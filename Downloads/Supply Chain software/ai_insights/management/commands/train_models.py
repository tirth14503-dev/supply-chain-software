from django.core.management.base import BaseCommand

from ai_insights.ml.train import train_all


class Command(BaseCommand):
    help = 'Train the AI Insights ML models (demand forecast, supplier risk, delay predictor, anomaly detector) on current data'

    def handle(self, *args, **options):
        train_all(log=self.stdout.write)
        self.stdout.write(self.style.SUCCESS('All models trained and saved to ai_insights/ml/artifacts/'))
