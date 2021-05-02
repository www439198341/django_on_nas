from django.db import models

# Create your models here.
from django.utils import timezone


class SubscriptionModel(models.Model):
    link = models.CharField(max_length=1000, verbose_name='链接')
    config = models.CharField(max_length=2000, verbose_name='配置')
    web_speed = models.FloatField(verbose_name='网页测速')
    download_speed = models.FloatField(verbose_name='下载测速')
    status = models.IntegerField(verbose_name='状态', default=0, help_text='链接状态.0-高速;1-低速;2-连续低速;3-未测试')
    source = models.CharField(max_length=1000, verbose_name='订阅来源')
    add_time = models.DateTimeField(default=timezone.now, verbose_name='添加时间')
    modify_time = models.DateTimeField(auto_now=True, verbose_name='修改时间')
    md5_info = models.CharField(max_length=100, verbose_name='配置信息md5值')

    class Meta:
        verbose_name = '配置信息'
        verbose_name_plural = verbose_name

    def __str__(self):
        return self.link
