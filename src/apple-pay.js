// Проверяем поддерживает ли устройство возможность совершать платежи с помощью Apple Pay
// И показываем кнопку Apple Pay в случае если устройство не только поддерживается но и настроена хотя бы одна карта
if (window.ApplePaySession) {
    //  Тут наш идинтификатор который мв зарегестрировали в Apple Dev Console
    var merchantIdentifier = 'merchant.ru.tinkoff.oplata.1496667497923';
    var promise = ApplePaySession.canMakePaymentsWithActiveCard(merchantIdentifier);
    promise.then(function (canMakePayments) {
        if (canMakePayments) {
            console.log("W0W! Its Apple time !");
            $('#apple-pay-button').css('visibility', 'visible');
        }
    });
}

// И вот пользователь нажал кнопку !
$('#apple-pay-button').click(function () {
    var request = {
        countryCode: 'RU',
        currencyCode: 'RUB',
        supportedNetworks: ['visa', 'masterCard'],
        merchantCapabilities: ['supports3DS'],
        total: { label: 'Sochi-Online', amount: '{{ sum }}.00' },
    }
    // Начниаем сессию
    var session = new ApplePaySession(3, request);

    session.onvalidatemerchant = function (event) {

        var data = {
            validationUrl: event.validationURL,
            csrfmiddlewaretoken: '{{ csrf_token }}'
        };
        // Apple из своих внутренностей берет url (validationUrl), мы берем этот url
        //  и с ним идем на наш бэкенд,  см. view.py - class ApplePayStartSession(View)
        // Тем самым мы проходим валидаци, что нам вообще можно совершать платежи
        // Плюс получили от Apple JSON в котором в зашифрованном виде хранится данные
        // о карте с помощью которой совершен платеж (мы их не видим, ключи расшифровки
        // этих данных есть только у Тинькова) плюс сумма платежа
        $.post("{% url 'pay:apple_pay_startsession' %}", data).then(function (result) {
            session.completeMerchantValidation(result);
        });
    };

    // Если валидация выше прошла успешно, то приступаем к финишному этапу
    // Здесь немного наших внутрнних данных, но главное это EncryptedPaymentData
    // Эти данные мы снова шлем на наш бэкенд см. view.py - class ApplePayFinishSession(View)
    // Там происходит магия, часть которой я описал в комментариях и на финише мы получаем
    // ответ от бэкенда, если все хорошо - показываем страничку об успешной оплате, если нет
    // то говорим, классической фразой, что что-то пошло не так :)))
    session.onpaymentauthorized = function (event) {

        var merchantAuthorizeURL = "{% url 'pay:apple_pay_finishsession' %}",
            data = {
                        EncryptedPaymentData: btoa(JSON.stringify(event.payment.token.paymentData)),
                        Amount: "{{ sum }}",
                        Dogovor: "{{ dogovor}}",
                        fio: "{{ fio}}",
                        email: "{{ email }}",
                        phone: "{{ phone }}",
                        OrderId: "{{ dogovor }}-{{ pay_id_time }}",
                        csrfmiddlewaretoken: "{{ csrf_token }}"
                        };
            $.post(merchantAuthorizeURL, data).then(function (result) {
                var status;
                var redir;
                if (result.Success) {
                    status = ApplePaySession.STATUS_SUCCESS;
                    redir = "{% url 'pay:tnkff_success' %}?orderid={{ dogovor }}-{{ pay_id_time }}";
                } else {
                    status = ApplePaySession.STATUS_FAILURE;
                    redir = "{% url 'pay:tnkff_fail' %}";
                };
                session.completePayment(status);
                //Тут перед ридеректом вставляем небольшую паузу, что-бы дождаться пока прилетит
                // нотификация о платеже от Тинькова, что-бы в результатах дать более полную инфу о платеже
                // но если она не прилетит - тоже не страшно, но это уже совсем другая история
                setTimeout(function () {
                    window.location.href = redir;
                }, 4000);
            });
    };
    // Начало сессии Apple Pay
    session.begin();
});
