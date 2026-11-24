from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import UserProfile
from apps.engine.models import AttemptResponse, AttemptStatus, ExaminationAttempt
from apps.examinations.models import AnswerRevealPolicy, Examination, ExaminationQuestion, ExaminationSection
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
        self.section = ExaminationSection.objects.create(exam=self.exam, title='Mathematics', order=1)
        self.client = APIClient()

    def staff_url(self, action):
        return reverse(f'analytics:{action}', args=[self.exam.pk])

    def question(self, key, kind=QuestionType.MCQ_SINGLE, is_cancelled=False,
                 numerical_min=None, numerical_max=None, section=None):
        target_section = section or self.section
        question = Question.objects.create(
            question_bank=self.bank,
            content_text='Question content',
            key=key,
            question_type=kind,
            is_cancelled=is_cancelled,
            numerical_min=numerical_min,
            numerical_max=numerical_max,
        )
        ExaminationQuestion.objects.create(
            exam_section=target_section,
            question=question,
            marks=4,
            negative_marks=-1,
            partial_marks=1,
        )
        return question

    def attempt(self, user, answers, numerical_answers=None, status=AttemptStatus.SUBMITTED):
        now = timezone.now()
        attempt = ExaminationAttempt.objects.create(
            user=user,
            examination=self.exam,
            status=status,
            submitted_at=now,
            server_deadline=now - timedelta(minutes=1),
        )
        if answers:
            for question, choices in answers.items():
                AttemptResponse.objects.create(attempt=attempt, question=question, selected_options=choices)
        if numerical_answers:
            for question, num_val in numerical_answers.items():
                AttemptResponse.objects.create(attempt=attempt, question=question, numerical_value=num_val)
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

    def test_scoring_numerical_tolerance_and_one_word(self):
        q_num = self.question('4', QuestionType.NUMERICAL)
        q_word = self.question('Gravity', QuestionType.ONE_WORD)

        # Candidate with answers within tolerance and matching case-insensitively
        att = self.attempt(
            self.student,
            {},
            numerical_answers={q_num: '4.008', q_word: 'gravity'}
        )
        self.client.force_authenticate(self.staff)
        self.client.post(self.staff_url('evaluate'))
        res = Result.objects.get(attempt=att)
        self.assertEqual(res.total_score, Decimal('8.00'))  # 4 + 4

        # Peer with answer outside tolerance and wrong word
        att_bad = self.attempt(
            self.peer,
            {},
            numerical_answers={q_num: '4.05', q_word: 'levity'}
        )
        self.client.post(self.staff_url('evaluate'))
        res_bad = Result.objects.get(attempt=att_bad)
        self.assertEqual(res_bad.total_score, Decimal('-2.00'))  # -1 + -1
        self.assertEqual(res_bad.penalty, Decimal('2.00'))

    def test_cancelled_question_awards_full_bonus_marks(self):
        q_cancelled = self.question('A', QuestionType.MCQ_SINGLE, is_cancelled=True)
        # Student leaves it completely empty
        att = self.attempt(self.student, {})
        self.client.force_authenticate(self.staff)
        resp = self.client.post(self.staff_url('evaluate'))
        self.assertEqual(resp.status_code, 200)

        res = Result.objects.get(attempt=att)
        self.assertEqual(res.total_score, Decimal('4.00'))
        self.assertEqual(res.maximum_score, Decimal('4.00'))

    def test_multi_mcq_wrong_choice_overrides_partial(self):
        q_multi = self.question('A+C', QuestionType.MCQ_MULTI)
        # Candidate picks A (correct) and B (incorrect)
        att = self.attempt(self.student, {q_multi: ['A', 'B']})
        self.client.force_authenticate(self.staff)
        self.client.post(self.staff_url('evaluate'))
        res = Result.objects.get(attempt=att)
        self.assertEqual(res.total_score, Decimal('-1.00'))
        self.assertEqual(res.penalty, Decimal('1.00'))

    def test_tie_breaking_order_sections_and_dob(self):
        sec_physics = ExaminationSection.objects.create(exam=self.exam, title='Physics', order=2)
        q_math = self.question('A', section=self.section)       # Math +4
        q_phys = self.question('B', section=sec_physics)       # Physics +4

        # Candidate A: Math = 4, Phys = 0 -> Total = 4
        # Candidate B: Math = 0, Phys = 4 -> Total = 4
        # Candidate A should win tie-break due to higher Math (Section 1) score
        att_a = self.attempt(self.student, {q_math: ['A']})
        att_b = self.attempt(self.peer, {q_phys: ['B']})

        self.client.force_authenticate(self.staff)
        self.client.post(self.staff_url('evaluate'))
        res_a = Result.objects.get(attempt=att_a)
        res_b = Result.objects.get(attempt=att_b)
        self.assertEqual(res_a.rank, 1)
        self.assertEqual(res_b.rank, 2)

        # Next: Test DOB tie-break when scores and sections are identical
        users = get_user_model().objects
        u_old = users.create_user('older_cand', organization=self.org)
        u_young = users.create_user('younger_cand', organization=self.org)
        UserProfile.objects.create(user=u_old, full_name='Older Cand', metadata={'dob': '2000-01-01'})
        UserProfile.objects.create(user=u_young, full_name='Younger Cand', metadata={'dob': '2005-01-01'})

        # Same exam, equal scores
        exam2 = Examination.all_objects.create(organization=self.org, name='DOB Exam')
        sec_m = ExaminationSection.objects.create(exam=exam2, title='General', order=1)
        q = Question.objects.create(question_bank=self.bank, content_text='Q', key='A', question_type=QuestionType.MCQ_SINGLE)
        ExaminationQuestion.objects.create(exam_section=sec_m, question=q, marks=4, negative_marks=-1)

        now = timezone.now()
        att_o = ExaminationAttempt.objects.create(user=u_old, examination=exam2, status=AttemptStatus.SUBMITTED, server_deadline=now)
        att_y = ExaminationAttempt.objects.create(user=u_young, examination=exam2, status=AttemptStatus.SUBMITTED, server_deadline=now)
        AttemptResponse.objects.create(attempt=att_o, question=q, selected_options=['A'])
        AttemptResponse.objects.create(attempt=att_y, question=q, selected_options=['A'])

        self.client.post(reverse('examinations-evaluate', args=[exam2.pk]))
        res_o = Result.objects.get(attempt=att_o)
        res_y = Result.objects.get(attempt=att_y)
        self.assertEqual(res_o.rank, 1)
        self.assertEqual(res_y.rank, 2)

    def test_answer_reveal_policies(self):
        q = self.question('A')
        att = self.attempt(self.student, {q: ['A']})
        self.client.force_authenticate(self.staff)
        self.client.post(self.staff_url('evaluate'))

        report_url = reverse('attempt-report', args=[att.pk])

        # 1. IMMEDIATELY policy: student sees answer and explanation
        self.exam.answer_reveal_policy = AnswerRevealPolicy.IMMEDIATELY
        self.exam.save(update_fields=['answer_reveal_policy'])
        self.client.force_authenticate(self.student)
        res = self.client.get(report_url).json()
        self.assertEqual(res['status'], 'SUCCESS')
        self.assertEqual(res['reviews'][0]['answer'], ['A'])

        # 2. NEVER policy: student gets empty answer and explanation
        self.exam.answer_reveal_policy = AnswerRevealPolicy.NEVER
        self.exam.save(update_fields=['answer_reveal_policy'])
        res_never = self.client.get(report_url).json()
        self.assertEqual(res_never['reviews'][0]['answer'], [])
        self.assertEqual(res_never['reviews'][0]['explanation'], '')

        # Staff can always see answer and explanation even if policy is NEVER
        self.client.force_authenticate(self.staff)
        res_staff = self.client.get(report_url).json()
        self.assertEqual(res_staff['reviews'][0]['answer'], ['A'])

        # 3. AFTER_CLOSE policy: hidden before end window, revealed after
        self.exam.answer_reveal_policy = AnswerRevealPolicy.AFTER_CLOSE
        self.exam.end_window = timezone.now() + timedelta(hours=2)
        self.exam.save(update_fields=['answer_reveal_policy', 'end_window'])
        self.client.force_authenticate(self.student)
        res_before = self.client.get(report_url).json()
        self.assertEqual(res_before['reviews'][0]['answer'], [])

        # Window closes
        self.exam.end_window = timezone.now() - timedelta(minutes=5)
        self.exam.save(update_fields=['end_window'])
        res_after = self.client.get(report_url).json()
        self.assertEqual(res_after['reviews'][0]['answer'], ['A'])

    def test_direct_api_endpoints_evaluate_results_and_report(self):
        q = self.question('C')
        att = self.attempt(self.student, {q: ['C']})

        # POST /api/v1/examinations/{id}/evaluate/
        self.client.force_authenticate(self.staff)
        eval_res = self.client.post(f'/api/v1/examinations/{self.exam.pk}/evaluate/')
        self.assertEqual(eval_res.status_code, 200)
        self.assertEqual(eval_res.json()['status'], 'SUCCESS')
        self.assertIn('summary', eval_res.json())
        self.assertEqual(len(eval_res.json()['summary']['rankings']), 1)

        # GET /api/v1/examinations/{id}/results/
        res_res = self.client.get(f'/api/v1/examinations/{self.exam.pk}/results/')
        self.assertEqual(res_res.status_code, 200)
        self.assertIn('rankings', res_res.json())
        self.assertIn('score_distribution', res_res.json())

        # GET /api/v1/attempts/{id}/report/
        self.client.force_authenticate(self.student)
        rep_res = self.client.get(f'/api/v1/attempts/{att.pk}/report/')
        self.assertEqual(rep_res.status_code, 200)
        self.assertEqual(rep_res.json()['report']['total_score'], 4.0)
        self.assertEqual(rep_res.json()['report']['rank'], 1)
        self.assertEqual(rep_res.json()['report']['percentile'], 100.0)
