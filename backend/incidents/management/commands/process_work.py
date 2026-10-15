from django.core.management.base import BaseCommand, CommandError
from incidents.services import process_simulated_work

class Command(BaseCommand):
    help = 'Run one durable simulation work pass and expire crew offers; no external calls.'
    def add_arguments(self, parser):
        parser.add_argument('--max-jobs', type=int, default=100,
                            help='Bound notification jobs per pass. Default 100.')
    def handle(self, *args, **options):
        limit = options['max_jobs']
        if not 1 <= limit <= 10000:
            raise CommandError('--max-jobs must be between 1 and 10000.')
        count = process_simulated_work(limit=limit)
        self.stdout.write(f'Simulation pass completed: {count} notification attempts. Manual handoffs/escalations remain visible.')
