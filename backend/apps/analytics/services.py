from collections import Counter, defaultdict
from datetime import date
from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.utils import timezone

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
    except (InvalidOperation, TypeError, ValueError):
        return None
    return number if number.is_finite() else None


def grade_question(question, options, value, positive, negative, partial):
    """
    Grade candidate response against question key and marking scheme.
    Rules:
    - Single MCQ: Correct option matches -> +positive_marks, wrong -> -negative_marks, empty -> UNANSWERED (0 marks).
    - Multi-select MCQ: All correct -> +positive_marks, partial subset with partial marks enabled -> +partial_marks * count(selected) up to positive_marks, any wrong selection -> -negative_marks.
    - Numerical / Single-digit: Within [numerical_min, numerical_max] or exact tolerance -> +positive_marks, outside -> 0 or negative penalty.
    - One-word / Fill-in-the-blank: Case-insensitive match -> +positive_marks, mismatch -> -negative_marks.
    - Cancelled questions (is_cancelled=True): Award full bonus marks to all candidates without penalizing maximum possible score.
    """
    if getattr(question, 'is_cancelled', False):
        return Outcome.CANCELLED, positive, []

    kind = normalize_question_type(question.question_type)
    if kind in (QuestionType.SUBJECTIVE, QuestionType.CODING):
        return Outcome.PENDING, ZERO, []

    if kind in (QuestionType.NUMERICAL, QuestionType.SINGLE_DIGIT):
        expected = decimal_value(question.key)
        has_min = question.numerical_min is not None
        has_max = question.numerical_max is not None
        lower = decimal_value(question.numerical_min) if has_min else expected
        upper = decimal_value(question.numerical_max) if has_max else expected

        # If min/max not explicitly specified, apply precision tolerance of 0.01 around expected key
        if not has_min and not has_max and expected is not None:
            lower = expected - Decimal('0.01')
            upper = expected + Decimal('0.01')

        answer = [str(expected if expected is not None else lower)] if expected is not None else ([str(lower), str(upper)] if lower is not None and upper is not None else [])
        if not answer:
            return Outcome.PENDING, ZERO, answer
        if not value or not str(value).strip():
            return Outcome.UNANSWERED, ZERO, answer
        number = decimal_value(str(value).strip())
        if number is not None and lower is not None and upper is not None and lower <= number <= upper:
            return Outcome.CORRECT, positive, answer
        return Outcome.INCORRECT, -negative, answer

    if kind == QuestionType.ONE_WORD:
        key_str = (question.key or '').strip()
        answer = [key_str] if key_str else []
        if not answer:
            return Outcome.PENDING, ZERO, answer
        if not value or not str(value).strip():
            return Outcome.UNANSWERED, ZERO, answer
        if str(value).strip().casefold() == key_str.casefold():
            return Outcome.CORRECT, positive, answer
        return Outcome.INCORRECT, -negative, answer

    configured_options = list(question.options.all())
    correct = {option.option_key.strip().upper() for option in configured_options if option.is_correct}
    if not correct:
        key_raw = question.key or ''
        correct = {k.strip().upper() for k in key_raw.replace(',', '+').split('+') if k.strip()}
    answer = sorted(correct)
    if not correct:
        return Outcome.PENDING, ZERO, answer
    if not options:
        return Outcome.UNANSWERED, ZERO, answer

    option_ids = {str(option.pk).upper(): option.option_key.strip().upper() for option in configured_options}
    choices = {option_ids.get(str(option).strip().upper(), str(option).strip().upper()) for option in options if str(option).strip()}
    if not choices:
        return Outcome.UNANSWERED, ZERO, answer

    if kind == QuestionType.MCQ_MULTI:
        if choices == correct:
            return Outcome.CORRECT, positive, answer
        if choices < correct and partial > ZERO:
            awarded = min(positive, partial * Decimal(len(choices)))
            return Outcome.PARTIAL, awarded, answer
        return Outcome.INCORRECT, -negative, answer

    # Single MCQ
    if choices == correct and len(choices) == 1:
        return Outcome.CORRECT, positive, answer
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
    # Idempotent re-evaluation: purge any previous result for this attempt
    Result.objects.filter(attempt=attempt).delete()

    responses = {response.question_id: response for response in attempt.responses.all()}
    result = Result.objects.create(attempt=attempt, total_score=ZERO, maximum_score=ZERO, penalty=ZERO)
    scorecard = Scorecard.objects.create(result=result, score_percentage=ZERO)

    for title, order, questions in sections:
        section = SectionScore(scorecard=scorecard, title=title, order=order, score=ZERO, maximum_score=ZERO)
        reviews = []
        for question, positive, negative, partial in questions:
            positive, negative, partial = (Decimal(str(marks)).quantize(Decimal('0.01'))
                                           for marks in (positive, negative, partial))
            response = responses.get(question.pk)
            raw_options = response.selected_options if response else []
            options = [str(opt) for opt in raw_options] if isinstance(raw_options, list) else []
            value = (response.numerical_value or '').strip() if response else ''
            outcome, marks, answer = grade_question(question, options, value, positive, abs(negative), partial)

            section.maximum_score += positive
            section.score += marks
            result.penalty += max(ZERO, -marks)
            reviews.append(QuestionResponseReview(
                section=section,
                question=question,
                selected_options=options,
                submitted_value=value,
                answer=answer,
                explanation=question.explanation or '',
                outcome=outcome,
                marks=marks,
                time_spent_seconds=max(0, response.time_spent_seconds) if response else 0,
            ))
        section.save()
        QuestionResponseReview.objects.bulk_create(reviews)
        result.total_score += section.score
        result.maximum_score += section.maximum_score

    result.save(update_fields=['total_score', 'maximum_score', 'penalty'])
    if result.maximum_score > ZERO:
        scorecard.score_percentage = (Decimal(100) * result.total_score / result.maximum_score).quantize(Decimal('0.01'))
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
    """
    Deterministic tie-breaking hierarchy:
    1. Higher total score (descending)
    2. Higher Section 1 (Mathematics / first section) score (descending)
    3. Higher Section 2 (Physics / second section) score (descending)
    4. Fewer negative penalty marks (ascending)
    5. Candidate age / DOB (older candidate ranked higher -> earlier birth date ascending)
    6. Attempt ID (string ascending)
    """
    sections = list(result.scorecard.sections.all())
    scores = {section.title.strip().casefold(): section.score for section in sections}
    math = next((scores[name] for name in ('mathematics', 'maths', 'math') if name in scores), None)
    primary = math if math is not None else (sections[0].score if sections else ZERO)
    secondary = scores.get('physics', sections[1].score if len(sections) > 1 else ZERO)
    return (
        -result.total_score,
        -primary,
        -secondary,
        result.penalty,
        birth_date(result.attempt.user),
        str(result.attempt_id),
    )


def rank_results(results):
    """
    Deterministic ranking and percentile calculation:
    Percentile = (Count(candidates with score <= S) / N) * 100, rounded to 3 decimal places.
    """
    if not results:
        return
    total = len(results)
    counts = Counter(result.total_score for result in results)
    percentiles = {}
    cumulative = 0
    for score in sorted(counts):
        cumulative += counts[score]
        percentiles[score] = (Decimal(100) * cumulative / Decimal(total)).quantize(Decimal('0.001'))

    for rank, result in enumerate(sorted(results, key=ranking_key), start=1):
        result.rank = rank
        result.percentile = percentiles[result.total_score]
    Result.objects.bulk_update(results, ['rank', 'percentile'])


def cohort_results(exam):
    return Result.objects.filter(
        attempt__examination=exam,
        attempt__user__organization_id=exam.organization_id,
        attempt__status__in=FINAL_STATUSES,
    )


@transaction.atomic
def evaluate_examination(exam_id):
    """Grade final attempts and refresh cohort ranks under the examination row lock."""
    exam = Examination.all_objects.select_for_update().get(pk=exam_id)
    sections = examination_sections(exam)
    attempts = ExaminationAttempt.objects.filter(
        examination=exam,
        user__organization_id=exam.organization_id,
        status__in=FINAL_STATUSES,
    ).select_related('examination', 'user__profile').prefetch_related('responses')

    for attempt in attempts:
        evaluate_attempt(attempt, sections)

    results = list(cohort_results(exam).select_related(
        'attempt__user__profile', 'scorecard',
    ).prefetch_related('scorecard__sections'))
    rank_results(results)
    return len(results)


def build_examination_summary(exam):
    """Construct complete cohort evaluation summary, leaderboard, and statistics."""
    results = list(cohort_results(exam).select_related(
        'attempt__user__profile', 'scorecard',
    ).prefetch_related('scorecard__sections__reviews').order_by('rank', 'pk'))

    total_candidates = len(results)
    rankings_data = []

    for res in results:
        reviews = []
        sec_scores = {}
        total_correct = 0
        total_incorrect = 0
        for sec in res.scorecard.sections.all():
            sec_scores[sec.title] = {
                'score': float(sec.score),
                'maximum_score': float(sec.maximum_score),
                'order': sec.order,
            }
            for rev in sec.reviews.all():
                is_correct = rev.outcome in (Outcome.CORRECT, Outcome.CANCELLED)
                is_incorrect = rev.outcome == Outcome.INCORRECT
                if is_correct:
                    total_correct += 1
                if is_incorrect:
                    total_incorrect += 1
                reviews.append({
                    'question_id': rev.question_id,
                    'section': sec.title,
                    'marks_awarded': float(rev.marks),
                    'is_correct': is_correct,
                    'is_attempted': rev.outcome != Outcome.UNANSWERED,
                    'outcome': rev.outcome,
                    'explanation': rev.explanation,
                })

        cand_name = res.attempt.user.get_full_name() or res.attempt.user.username
        rankings_data.append({
            'attempt_id': str(res.attempt_id),
            'candidate_id': str(res.attempt.user_id),
            'candidate_name': cand_name,
            'student': cand_name,
            'username': res.attempt.user.username,
            'total_score': float(res.total_score),
            'maximum_score': float(res.maximum_score),
            'penalty': float(res.penalty),
            'total_correct': total_correct,
            'total_incorrect': total_incorrect,
            'rank': res.rank,
            'percentile': float(res.percentile) if res.percentile is not None else 100.0,
            'section_scores': sec_scores,
            'question_reviews': reviews,
        })

    highest = float(results[0].total_score) if results else 0.0
    lowest = float(results[-1].total_score) if results else 0.0
    avg_score = float(round(sum(r.total_score for r in results) / total_candidates, 2)) if total_candidates else 0.0

    return {
        'exam_id': str(exam.pk),
        'evaluated_at': timezone.now().isoformat(),
        'total_candidates': total_candidates,
        'highest_score': highest,
        'lowest_score': lowest,
        'average_score': avg_score,
        'rankings': rankings_data,
    }
