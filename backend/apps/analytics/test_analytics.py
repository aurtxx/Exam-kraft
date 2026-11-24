from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.engine.models import AttemptResponse, AttemptStatus, ExaminationAttempt
from apps.examinations.models import Examination, ExaminationQuestion, ExaminationSection
from apps.organizations.models import Organization
from apps.question_bank.models import Question, QuestionBank, QuestionType

from .models import QuestionResponseReview, Result


class AnalyticsTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name='School', slug='school')
        users = get_user_model().objects
        self.staff = users.create_user('teacher', organization=self.org, role='FACULTY')
        self.student = users.create_user('student', organization=self.org)
        self.peer = users.create_user('peer', organization=self.org)
        other_org = Organization.objects.create(name='Other school', slug='other')
        self.outsider = users.create_user('outsider', organization=other_org, role='FACULTY')
        self.exam = Examination.all_objects.create(organization=self.org, name='Test exam')
        self.bank = QuestionBank.all_objects.create(organization=self.org, name='Question bank')
        self.section = ExaminationSection.objects.create(exam=self.exam, title='Mathematics')
        self.client = APIClient()

    def staff_url(self, action):
        return reverse(f'analytics:{action}', args=[self.exam.pk])

    def question(self, key, kind=QuestionType.MCQ_SINGLE):
        question = Question.objects.create(
            question_bank=self.bank, content_text='Question', key=key, question_type=kind,
        )
        ExaminationQuestion.objects.create(
            exam_section=self.section, question=question, marks=4, negative_marks=-1, partial_marks=1,
        )
        return question

    def attempt(self, user, answers, status=AttemptStatus.SUBMITTED):
        now = timezone.now()
        attempt = ExaminationAttempt.objects.create(
            user=user, examination=self.exam, status=status, submitted_at=now,
            server_deadline=now - timedelta(minutes=1),
        )
        for question, choices in answers.items():
            AttemptResponse.objects.create(attempt=attempt, question=question, selected_options=choices)
        return attempt

    def test_evaluation_ranking_publication_and_download(self):
        multi = self.question('A+C+D', QuestionType.MCQ_MULTI)
        single = self.question('B')
        wrong = self.question('D')
        self.question('C')
        first = self.attempt(self.student, {multi: ['A', 'C'], single: ['B'], wrong: ['B']})
        second = self.attempt(self.peer, {multi: ['A', 'C', 'D'], single: ['A'], wrong: ['D']},
                              status=AttemptStatus.AUTO_SUBMITTED)

        self.client.force_authenticate(self.outsider)
        self.assertEqual(self.client.get(self.staff_url('report')).status_code, 404)
        self.assertEqual(self.client.post(self.staff_url('evaluate')).status_code, 404)

        self.client.force_authenticate(self.staff)
        self.assertEqual(self.client.post(self.staff_url('evaluate')).data['evaluated_count'], 2)
        self.assertEqual(self.client.post(self.staff_url('evaluate')).data['evaluated_count'], 2)
        result = Result.objects.get(attempt=first)
        self.assertEqual((result.total_score, result.penalty, result.rank, result.percentile),
                         (Decimal('5'), Decimal('1'), 2, Decimal('50')))
        self.assertEqual(Result.objects.get(attempt=second).rank, 1)
        self.assertEqual(self.client.get(self.staff_url('report')).data['summary']['candidates'], 2)
        self.assertEqual(self.client.get(self.staff_url('rank-list')).data[0]['candidate_id'], str(self.peer.pk))

        self.client.force_authenticate(self.student)
        url = reverse('analytics:scorecard', args=[result.pk])
        self.assertEqual(self.client.get(url).status_code, 404)
        self.assertEqual(self.client.get(self.staff_url('rank-list')).status_code, 403)

        self.client.force_authenticate(self.staff)
        self.assertEqual(self.client.post(self.staff_url('publish')).data['published_count'], 2)
        self.exam.hide_rank = True
        self.exam.save(update_fields=['hide_rank'])

        self.client.force_authenticate(self.student)
        card = self.client.get(url).data
        self.assertIsNone(card['result']['rank'])
        self.assertEqual([review['outcome'] for review in card['sections'][0]['reviews']], [
            QuestionResponseReview.Outcome.PARTIAL, QuestionResponseReview.Outcome.CORRECT,
            QuestionResponseReview.Outcome.INCORRECT, QuestionResponseReview.Outcome.UNANSWERED,
        ])
        download = self.client.get(reverse('analytics:scorecard-download', args=[result.pk]))
        self.assertEqual(download.status_code, 200)
        self.assertIn(b'Mathematics,5.00,16.00', download.content)
        self.client.force_authenticate(self.peer)
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_ties_share_percentile_and_fewer_penalties_win(self):
        multi = self.question('A+B+C', QuestionType.MCQ_MULTI)
        single = self.question('D')
        clean = self.attempt(self.student, {multi: ['A', 'B', 'C']})
        penalized = self.attempt(self.peer, {multi: ['A', 'B', 'C'], single: ['A']})
        # Give the second candidate one partial mark to offset the penalty.
        extra = self.question('A+B', QuestionType.MCQ_MULTI)
        AttemptResponse.objects.create(attempt=penalized, question=extra, selected_options=['A'])

        self.client.force_authenticate(self.staff)
        self.assertEqual(self.client.post(self.staff_url('evaluate')).status_code, 200)
        results = list(Result.objects.order_by('rank'))
        self.assertEqual([result.attempt_id for result in results], [clean.pk, penalized.pk])
        self.assertEqual([result.percentile for result in results], [Decimal('100'), Decimal('100')])
