# В этом классе мы должны доказать Apple что мы - именно за кого себя принимаем
# В описании от Apple это называется *Providing Merchant Validation*
# Тут на входе только validationUrl, например  apple-pay-gateway-nc-pod5.apple.com

class ApplePayStartSession(View):
    http_method_names = ['post']

    def post(self, request):
        if 'validationUrl' in request.POST and request.POST['validationUrl']:
            validationurl = request.POST['validationUrl']
        else:
            # Если прилетают не все параметры - отвечаем 404
            return HttpResponse("What ?!", status=404)

        # Проверяем, идет ли запрос на *.apple.com, для параноиков :)
        get_url = tldextract.extract(validationurl)
        if get_url.domain != 'apple' or get_url.suffix != 'com':
            return HttpResponse("No way, man !", status=404)

        # Тут формируем запрос по правилам Apple
        merchant_msg = {
            "merchantIdentifier": "merchant.ru.tinkoff.oplata.1496667497923",
            "displayName": "Sochi-Online",
            "initiative": "web",
            "initiativeContext": request.META['HTTP_HOST']
        }

        # Находим директорию с сертификатом
        module_dir = os.path.dirname(__file__)
        ca = os.path.join(module_dir, 'ca/merchant_id.pem')

        # *Магия здесь* - делаем запрос на URL который нам вернул Apple  чуть выше, с подписаным сертификатом!
        # Только с ним и только так нам от Apple нам придет то что нужно, иначе - куча ошибок
        req = requests.post(validationurl, json=merchant_msg, cert=ca)

        # Если ответ - 200, возвращаем его на фронтенд
        if req.status_code == 200:
            return HttpResponse(req.text, content_type="application/json")
        else:
            return HttpResponse("Error", status=404)


# Этот класс запускается в момент нажатия кнопки Apple Pay
class ApplePayFinishSession(View):
    http_method_names = ['post']

    # Внутренние дела, проверяю что-бы в запросе были все параметры, пускай даже пустые но были
    def post(self, request, *args, **kwargs):
        if 'EncryptedPaymentData' not in request.POST or \
                'Dogovor' not in request.POST or \
                'OrderId' not in request.POST or \
                'Amount' not in request.POST or \
                'email' not in request.POST or \
                'fio' not in request.POST or \
                'phone' not in request.POST:
            return HttpResponseBadRequest()

        # Внутренние дела, выходим если случайно прилетел не существующий номер договора
        if not User.objects.filter(username=request.POST['Dogovor']).exists():
            return HttpResponseBadRequest()

        # На основании полученных данных формируем словарь для инициализации нового платежа в Tinkoff
        uzer = User.objects.get(username=request.POST['Dogovor'])
        init_post_data = {'TerminalKey': settings.TNK_TERMINAL_KEY_MOBI,
                          'Amount': str(int(request.POST['Amount']) * 100),
                          'OrderId': request.POST['OrderId'],
                          'DATA': {"Email": request.POST['email'],
                                   "Phone": request.POST['phone'],
                                   "Name": request.POST['fio'],
                                   "Dogovor": uzer.username},
                          'Description': "Apple-Pay платеж за услуги связи по договору N{}".format(uzer.username)}

        # Генерируем токен для нового запроса (SHA256)
        init_post_data['Token'] = tinkoff_make_token(init_post_data, settings.TNK_PASS_MOBI)
        init_url = "https://securepay.tinkoff.ru/v2/Init"
        init_rq = requests.post(init_url, json=init_post_data)

        # Если что-то пошло не так с запросом - выходим
        if init_rq.status_code != 200 or not init_rq_json['Success'] or init_rq_json['ErrorCode'] != '0':
            return HttpResponseBadRequest()

        # Сохраняем данные ответа нового платежа, примерно такие:
        # {
        #     "Status": "NEW",
        #     "OrderId": "0-1549656204",
        #     "Success": true,
        #     "PaymentURL": "https://securepay.tinkoff.ru/xxx",
        #     "ErrorCode": "0",
        #     "Amount": 5500,
        #     "TerminalKey": "1549611143961",
        #     "PaymentId": "5673444"
        # }
        init_rq_json = init_rq.json()

        # Теперь формируем словарь на финиш платежа, EncryptedPaymentData - это  JSON
        # который прилетел нам от Apple, мы получили его на фронте, запаковали его в BASE64
        # и прислали его сюда, второй важный параметр PaymentId - это из запроса чуть выше
        # Важно понимать, что сумма списания которую мы формируем для Apple и для Тинькова
        # в 2х разных местах должна совпадать
        finish_post_data = {'EncryptedPaymentData': request.POST['EncryptedPaymentData'],
                            'TerminalKey': settings.TNK_TERMINAL_KEY_MOBI,
                            'PaymentId': init_rq_json['PaymentId'],
                            'DATA': {'ApplePayWeb': True}
                            }
        finis_api_url = 'https://securepay.tinkoff.ru/v2/FinishAuthorize'
        # *Важно!*  Финишный запрос тоже нужно подписать токеном, в официальной документации
        # от Тинькова об этом не слова, но это тоже нужно сделать
        finish_post_data['Token'] = tinkoff_make_token(finish_post_data, settings.TNK_PASS_MOBI)
        finish_rq = requests.post(finis_api_url, json=finish_post_data)

        # Если ответ вернулся нормальный - возвращаем его на фронт
        # Пример ответа без ошибок:
        # {
        #     "Success": true,
        #     "ErrorCode": "0",
        #     "TerminalKey": "1549611143961",
        #     "Status": "CONFIRMED",
        #     "PaymentId": "5673444",
        #     "OrderId": "0-1549656204",
        #     "Amount": 5500
        # }│
        if finish_rq.status_code == 200:
            return HttpResponse(finish_rq.text, content_type="application/json")
        else:
            return HttpResponseBadRequest()
