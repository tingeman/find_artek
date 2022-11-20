# -*- coding: utf_8 -*-

from __future__ import unicode_literals
# my_string = b"This is a bytestring"
# my_unicode = "This is an Unicode string"

from subprocess import Popen, PIPE
import os.path
import os

from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from django.contrib.auth.models import User
from find_artek.publications import models as pub_models

class Command(BaseCommand):
    args = 'None'
    help = 'Creates thumbnails for all publications in database, that does not already have a thumbnail.'

    def handle(self, *args, **options):
        
        current_user = User.objects.get(username='thin')
        pubs = pub_models.Publication.objects.all()

        for p in pubs:
            if p.file and p.file.file.name:
                fn = os.path.join(settings.MEDIA_ROOT,p.file.file.name)
                dn = os.path.dirname(fn)
                fn, ext = os.path.splitext( os.path.basename(p.file.file.name) )
                
                tdn = os.path.join(dn,'thumbs')
                tn = os.path.join(tdn,fn+'_thumb.jpg')
                if not os.path.exists(tn):
                    
                    self.stdout.write("{0}\n".format(os.path.basename(tn)))
                    
                    if not os.path.exists( tdn ):
                        os.mkdir(tdn)
                    
                    cmd = ["gm", "convert", 
                           os.path.join(dn,fn+ext)+"[0]",
                           "-resize", "400x400", '-quality', '90', tn]
                    
                    h = Popen(cmd)
                    h.wait()







