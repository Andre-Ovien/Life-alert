from django.core.management.base import BaseCommand
from incidents.services import process_simulated_work

class Command(BaseCommand):
    help = 'Process safe simulated notification/EMS work and expire crew offers. No external calls.'
    def handle(self, *args, **options):
        process_simulated_work()
        self.stdout.write('Simulated work processed; manual handoffs remain pending.')
