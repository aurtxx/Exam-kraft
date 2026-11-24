from collections import Counter, defaultdict
from datetime import date
from decimal import Decimal, InvalidOperation

from django.db import transaction

from apps.engine.models import AttemptStatus, ExaminationAttempt
from apps.examinations.models import Examination
from apps.question_bank.models import QuestionType, normalize_question_type

from .models import QuestionResponseReview, Result, Scorecard, SectionScore


Outcome = QuestionResponseReview.Outcome
ZERO = Decimal('0')
FINAL_STATUSES = (AttemptStatus.SUBMITTED, AttemptStatus.AUTO_SUBMITTED)


def decimal_value(value):
    try:
        number = Decimal(str(value))
    except InvalidOperation:
        return None
    return number if number.is_finite() else None


def grade_question(question, options, value, positive, negative, partial):
    if question.is_cancelled:
        return Outcome.CANCELLED, ZERO, []
    kind = normalize_question_type(question.question_type)
    if kind in (QuestionType.SUBJECTIVE, QuestionType.CODING):
        return Outcome.PENDING, ZERO, []
    if kind in (QuestionType.NUMERICAL, QuestionType.SINGLE_DIGIT):
        expected = decimal_value(question.key)
        lower = decimal_value(question.numerical_min) if question.numerical_min is not None else expected
        upper = decimal_value(question.numerical_max) if question.numerical_max is not None else expected
        answer = [str(lower), str(upper)] if lower is not None and upper is not None else []
        if not answer:
            return Outcome.PENDING, ZERO, answer
        if not value:
            return Outcome.UNANSWERED, ZERO, answer
        number = decimal_value(value)
        if number is not None and lower <= number <= upper:
            return Outcome.CORRECT, positive, answer
        return Outcome.INCORRECT, ZERO, answer
    if kind == QuestionType.ONE_WORD:
        answer = [question.key.strip()] if question.key.strip() else []
        if not answer:
            return Outcome.PENDING, ZERO, answer
        if not value:
            return Outcome.UNANSWERED, ZERO, answer
        if value.casefold() == answer[0].casefold():
            return Outcome.CORRECT, positive, answer
        return Outcome.INCORRECT, -negative, answer

    configured_options = list(question.options.all())
    correct = {option.option_key.strip().upper() for option in configured_options if option.is_correct}
    if not correct:
        correct = {key.strip().upper() for key in question.key.replace(',', '+').split('+') if key.strip()}
    answer = sorted(correct)
    if not correct:
        return Outcome.PENDING, ZERO, answer
    if not options:
        return Outcome.UNANSWERED, ZERO, answer
    option_ids = {str(option.pk).upper(): option.option_key.strip().upper() for option in configured_options}
    choices = {option_ids.get(option.strip().upper(), option.strip().upper()) for option in options}
    if choices == correct and (kind == QuestionType.MCQ_MULTI or len(choices) == 1):
        return Outcome.CORRECT, positive, answer
    if kind == QuestionType.MCQ_MULTI and choices < correct and partial > ZERO:
        return Outcome.PARTIAL, min(positive, partial * len(choices)), answer
    return Outcome.INCORRECT, -negative, answer


def examination_sections(exam):
    sections = list(exam.sections.prefetch_related('exam_questions__question__options'))
    if sections:
        return [
            (section.title, section.order, [
                (link.question, link.marks, link.negative_marks, link.partial_marks)
                for link in section.exam_questions.all()
            ])
            for section in sections
        ]

    groups = defaultdict(list)
    if exam.question_paper_id:
        questions = exam.question_paper.questions.select_related('section').prefetch_related('options')
        for question in questions:
            title = question.section_name or (question.section.name if question.section else 'General')
            groups[title].append((question, question.positive_marks, question.negative_marks, question.partial_marks))
    return [(title, order, questions) for order, (title, questions) in enumerate(groups.items(), start=1)]


def evaluate_attempt(attempt, sections):
    responses = {response.question_id: response for response in attempt.responses.all()}
    result = Result.objects.create(attempt=attempt, total_score=0, maximum_score=0, penalty=0)
    scorecard = Scorecard.objects.create(result=result, score_percentage=0)

    for title, order, questions in sections:
        section = SectionScore(scorecard=scorecard, title=title, order=order, score=ZERO, maximum_score=ZERO)
        reviews = []
        for question, positive, negative, partial in questions:
            positive, negative, partial = (Decimal(str(marks)).quantize(Decimal('0.01'))
                                           for marks in (positive, negative, partial))
            response = responses.get(question.pk)
            raw_options = response.selected_options if response else []
            options = [str(option) for option in raw_options] if isinstance(raw_options, list) else []
            value = (response.numerical_value or '').strip() if response else ''
            outcome, marks, answer = grade_question(question, options, value, positive, abs(negative), partial)
            if outcome != Outcome.CANCELLED:
                section.maximum_score += positive
            section.score += marks
            result.penalty += max(ZERO, -marks)
            reviews.append(QuestionResponseReview(
                section=section, question=question, selected_options=options, submitted_value=value,
                answer=answer, explanation=question.explanation, outcome=outcome, marks=marks,
                time_spent_seconds=max(0, response.time_spent_seconds) if response else 0,
            ))
        section.save()
        QuestionResponseReview.objects.bulk_create(reviews)
        result.total_score += section.score
        result.maximum_score += section.maximum_score

    result.save(update_fields=['total_score', 'maximum_score', 'penalty'])
    if result.maximum_score:
        scorecard.score_percentage = 100 * result.total_score / result.maximum_score
    if attempt.examination.passing_marks is not None:
        scorecard.passed = result.total_score >= attempt.examination.passing_marks
    scorecard.save(update_fields=['score_percentage', 'passed'])
    return result


def birth_date(user):
    profile = getattr(user, 'profile', None)
    metadata = profile.metadata if profile else None
    value = (metadata.get('date_of_birth') or metadata.get('dob')) if isinstance(metadata, dict) else None
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        return date.max


def ranking_key(result):
    sections = list(result.scorecard.sections.all())
    scores = {section.title.strip().casefold(): section.score for section in sections}
    math = next((scores[name] for name in ('mathematics', 'maths', 'math') if name in scores), None)
    primary = math if math is not None else (sections[0].score if sections else ZERO)
    secondary = scores.get('physics', sections[1].score if len(sections) > 1 else ZERO)
    return -result.total_score, -primary, -secondary, result.penalty, birth_date(result.attempt.user), result.attempt_id


def rank_results(results):
    counts = Counter(result.total_score for result in results)
    percentiles = {}
    cumulative = 0
    for score in sorted(counts):
        cumulative += counts[score]
        percentiles[score] = (Decimal(100) * cumulative / len(results)).quantize(Decimal('0.001'))
    for rank, result in enumerate(sorted(results, key=ranking_key), start=1):
        result.rank = rank
        result.percentile = percentiles[result.total_score]
    Result.objects.bulk_update(results, ['rank', 'percentile'])


def cohort_results(exam):
    return Result.objects.filter(
        attempt__examination=exam, attempt__user__organization_id=exam.organization_id,
        attempt__status__in=FINAL_STATUSES,
    )


@transaction.atomic
def evaluate_examination(exam_id):
    """Grade final attempts and refresh cohort ranks under the examination row lock."""
    exam = Examination.all_objects.select_for_update().get(pk=exam_id)
    sections = examination_sections(exam)
    attempts = ExaminationAttempt.objects.filter(
        examination=exam, user__organization_id=exam.organization_id, status__in=FINAL_STATUSES,
        result__isnull=True,
    ).select_related('examination').prefetch_related('responses')
    for attempt in attempts:
        evaluate_attempt(attempt, sections)

    results = list(cohort_results(exam).select_related(
        'attempt__user__profile', 'scorecard',
    ).prefetch_related('scorecard__sections'))
    rank_results(results)
    return len(results)
