import io
import zipfile
from PIL import Image
from django.test import TestCase
from django.contrib.auth import get_user_model
from apps.organizations.models import Organization
from apps.accounts.models import UserRole
from apps.question_bank.models import QuestionBank, Question, Option
from apps.question_bank.importers import ingest_zip_package, process_and_save_image

User = get_user_model()

class BulkZipIngestTestCase(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name="Test Institute", slug="test-inst")
        self.user = User.objects.create_user(
            username="faculty1",
            password="password123",
            organization=self.org,
            role=UserRole.FACULTY
        )
        self.paper = QuestionBank.objects.create(
            organization=self.org,
            name="JEE Mock 1",
            exam_type="JEE_MAIN"
        )

    def create_dummy_image_bytes(self, color='blue', size=(1600, 1200)):
        img = Image.new('RGB', size, color=color)
        buf = io.BytesIO()
        img.save(buf, format='PNG')
        return buf.getvalue()

    def test_direct_screenshot_zip_ingest(self):
        zip_buf = io.BytesIO()
        with zipfile.ZipFile(zip_buf, 'w') as zf:
            zf.writestr('q1_diagram.png', self.create_dummy_image_bytes('red'))
            zf.writestr('q2_circuit.png', self.create_dummy_image_bytes('green'))
            zf.writestr('q10_formula.png', self.create_dummy_image_bytes('blue'))
        
        zip_buf.seek(0)
        res = ingest_zip_package(zip_buf, self.paper, user=self.user, reason="Captured via Windows Screenshot Agent")
        
        self.assertEqual(res['mode'], 'SCREENSHOT_IMAGES')
        self.assertEqual(res['questions_created'], 3)
        
        questions = Question.objects.filter(question_bank=self.paper).order_by('question_number')
        self.assertEqual(questions.count(), 3)
        
        q1 = questions[0]
        self.assertTrue(q1.image_url.endswith('.webp'))
        self.assertTrue(q1.raw_image_url.endswith('.png'))
        self.assertEqual(q1.upload_metadata['uploaded_by'], 'faculty1')
        self.assertEqual(q1.upload_metadata['reason'], "Captured via Windows Screenshot Agent")
        self.assertEqual(q1.options.count(), 4)
