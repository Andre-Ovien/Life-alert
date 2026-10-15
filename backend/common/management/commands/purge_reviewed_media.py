from django.core.management.base import BaseCommand
from common.privacy import purge_media_due

class Command(BaseCommand):
    help='Purge only due local media covered by reviewed policy and approved requests. Dry run by default.'
    def add_arguments(self,parser):parser.add_argument('--apply',action='store_true')
    def handle(self,*args,**options):
        if not options['apply']:
            self.stdout.write('Dry run only. No files changed; --apply is required to process approved due local media.')
            return
        count=purge_media_due()
        self.stdout.write(f'Processed {count} approved local media/retired-blob purges. Holds/unknown policy stay retained.')
