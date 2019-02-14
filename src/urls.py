# -*- coding: utf-8 -*-
from django.conf.urls import url
from billing.pay import views

urlpatterns = [
    url(
        regex=r'^applestartsession/$',
        view=views.ApplePayStartSession.as_view(),
        name='apple_pay_startsession'
    ),
    url(
        regex=r'^applefinishsession/$',
        view=views.ApplePayFinishSession.as_view(),
        name='apple_pay_finishsession'
    ),
]
