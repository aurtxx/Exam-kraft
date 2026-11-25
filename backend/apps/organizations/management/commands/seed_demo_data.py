import os
from datetime import timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import FacultyProfile, User, UserProfile, UserRole
from apps.analytics.models import Result
from apps.analytics.services import evaluate_examination
from apps.engine.models import (
    AttemptResponse,
    AttemptStatus,
    ExaminationAttempt,
    ResponseStatus,
)
from apps.examinations.models import (
    CandidateAssignment,
    Examination,
    ExaminationQuestion,
    ExaminationSection,
    ExaminationStatus,
)
from apps.organizations.models import (
    Batch,
    BatchStream,
    ExaminationCenter,
    Organization,
    StudentBatchEnrollment,
)
from apps.question_bank.models import (
    Option,
    Question,
    QuestionBank,
    QuestionType,
    Section,
)


class Command(BaseCommand):
    help = "Seed deterministic and realistic demo dataset for Exam-Kraft reconstruction (Feature 26)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Force re-generation of demo records.",
        )
        parser.add_argument(
            "--candidates",
            type=int,
            default=110,
            help="Number of student candidates to seed (default: 110).",
        )
        parser.add_argument(
            "--password",
            type=str,
            default="",
            help="Override default user passwords.",
        )

    def _create_user(self, username, email, password, role, full_name, organization=None):
        is_priv = role == UserRole.SUPERADMIN
        user, created = User.objects.get_or_create(
            username=username,
            defaults={
                "email": email or username,
                "role": role,
                "organization": organization,
                "is_staff": is_priv,
                "is_superuser": is_priv,
            },
        )
        # Ensure password is set accurately
        user.set_password(password)
        user.role = role
        user.organization = organization
        user.is_staff = is_priv
        user.is_superuser = is_priv
        user.email = email or username
        user.save()

        UserProfile.objects.update_or_create(
            user=user,
            defaults={"full_name": full_name},
        )
        return user

    @transaction.atomic
    def handle(self, *args, **options):
        candidates_count = max(10, options["candidates"])
        super_pw = options["password"] or "Admin@123456"
        org_pw = options["password"] or "OrgAdmin@123456"
        fac_pw = options["password"] or "Faculty@123456"
        stu_pw = options["password"] or "Student@123456"

        self.stdout.write(self.style.NOTICE(">>> Starting Exam-Kraft Demo Data Seeding..."))

        # 1. Organizations
        org_ezexam, _ = Organization.objects.update_or_create(
            slug="ezexam-academy",
            defaults={"name": "Exam-Kraft Academy", "is_active": True},
        )
        org_apex, _ = Organization.objects.update_or_create(
            slug="apex-institute",
            defaults={"name": "Apex Technical Institute", "is_active": True},
        )

        # 2. Roles & Accounts
        superadmin = self._create_user(
            "superadmin@ezexam.local",
            "superadmin@ezexam.local",
            super_pw,
            UserRole.SUPERADMIN,
            "Platform Super Administrator",
            None,
        )
        orgadmin = self._create_user(
            "orgadmin@ezexam.local",
            "orgadmin@ezexam.local",
            org_pw,
            UserRole.ORG_ADMIN,
            "Exam-Kraft Org Administrator",
            org_ezexam,
        )
        faculty = self._create_user(
            "faculty@ezexam.local",
            "faculty@ezexam.local",
            fac_pw,
            UserRole.FACULTY,
            "Dr. Rajesh Sharma",
            org_ezexam,
        )
        # Additional OrgAdmin for Apex
        self._create_user(
            "orgadmin@apex.local",
            "orgadmin@apex.local",
            org_pw,
            UserRole.ORG_ADMIN,
            "Apex Org Administrator",
            org_apex,
        )

        # 3. Master Data: Batches & Centers
        batch_eng, _ = Batch.all_objects.update_or_create(
            organization=org_ezexam,
            code="ENG-12A",
            defaults={
                "name": "Class 12 - Engineering Batch A",
                "stream": BatchStream.JEE_MAIN,
                "is_active": True,
            },
        )
        batch_med, _ = Batch.all_objects.update_or_create(
            organization=org_ezexam,
            code="MED-12B",
            defaults={
                "name": "Class 12 - Medical Batch B",
                "stream": BatchStream.NEET,
                "is_active": True,
            },
        )

        center_main, _ = ExaminationCenter.all_objects.update_or_create(
            organization=org_ezexam,
            code="CENTER-MAIN",
            defaults={
                "name": "Main Campus Computer Lab (Capacity: 120)",
                "capacity": 120,
                "is_active": True,
            },
        )
        center_north, _ = ExaminationCenter.all_objects.update_or_create(
            organization=org_ezexam,
            code="CENTER-NORTH",
            defaults={
                "name": "North Annex Hall (Capacity: 80)",
                "capacity": 80,
                "is_active": True,
            },
        )

        # Configure Faculty Profile
        fac_profile, _ = FacultyProfile.objects.get_or_create(user=faculty)
        fac_profile.department = "Department of Pure & Applied Sciences"
        fac_profile.subjects = ["Mathematics", "Physics", "Chemistry", "General Aptitude"]
        fac_profile.save()
        fac_profile.assigned_batches.set([batch_eng, batch_med])
        fac_profile.assigned_centers.set([center_main, center_north])

        # 4. Students (10+ students and benchmark cohorts)
        student_users = []
        # Primary standard student
        primary_stu = self._create_user(
            "student@ezexam.local",
            "student@ezexam.local",
            stu_pw,
            UserRole.STUDENT,
            "Primary Demo Student",
            org_ezexam,
        )
        student_users.append(primary_stu)
        StudentBatchEnrollment.objects.update_or_create(
            batch=batch_eng,
            roll_number="STU-000",
            defaults={"student": primary_stu, "center": center_main, "is_active": True},
        )

        # Candidate 1 to 10 and beyond
        for i in range(1, candidates_count + 1):
            uname = f"candidate{i}@ezexam.local"
            cand_user = self._create_user(
                uname,
                uname,
                stu_pw,
                UserRole.STUDENT,
                f"Candidate {i:03d}",
                org_ezexam,
            )
            student_users.append(cand_user)
            roll = f"ROLL-{i:03d}"
            c = center_main if i <= 70 else center_north
            b = batch_eng if i % 2 == 1 else batch_med
            StudentBatchEnrollment.objects.update_or_create(
                batch=b,
                roll_number=roll,
                defaults={"student": cand_user, "center": c, "is_active": True},
            )

            # Also seed demo-apex student accounts for benchmark compatibility
            apex_uname = f"student{i:03d}@demo-apex.ezexam.example"
            apex_cand = self._create_user(
                apex_uname,
                apex_uname,
                stu_pw,
                UserRole.STUDENT,
                f"Apex Candidate {i:03d}",
                org_apex,
            )

        # 5. Question Banks & Varied Question Types
        qbank, _ = QuestionBank.all_objects.update_or_create(
            organization=org_ezexam,
            name="Comprehensive STEM & Aptitude Question Bank",
            defaults={
                "exam_type": "JEE_MAIN",
                "instructions": "Answer questions across Mathematics, Physics, Chemistry, and Aptitude.",
                "duration_minutes": 180,
                "created_by": faculty,
            },
        )

        # Define question content across subjects and types
        subject_data = {
            "Mathematics": [
                {
                    "type": QuestionType.MCQ_SINGLE,
                    "prompt": r"What is the derivative of $\sin(x)$ with respect to $x$?",
                    "options": [
                        ("A", r"$\cos(x)$", True),
                        ("B", r"$-\cos(x)$", False),
                        ("C", r"$\sin(x)$", False),
                        ("D", r"$-\sin(x)$", False),
                    ],
                    "key": "A",
                    "pos": 4.0,
                    "neg": 1.0,
                    "part": 0.0,
                },
                {
                    "type": QuestionType.MCQ_MULTI,
                    "prompt": r"Select all real roots of the quadratic equation $x^2 - 9 = 0$.",
                    "options": [
                        ("A", r"$-3$", True),
                        ("B", r"$0$", False),
                        ("C", r"$3$", True),
                        ("D", r"$9$", False),
                    ],
                    "key": "A,C",
                    "pos": 4.0,
                    "neg": 1.0,
                    "part": 2.0,
                },
                {
                    "type": QuestionType.NUMERICAL,
                    "prompt": r"Evaluate the arithmetic sum of the first ten positive integers: $\sum_{n=1}^{10} n$.",
                    "options": [],
                    "key": "55",
                    "min": 54.9,
                    "max": 55.1,
                    "pos": 4.0,
                    "neg": 0.0,
                    "part": 0.0,
                },
                {
                    "type": QuestionType.ONE_WORD,
                    "prompt": r"What is the mathematical term for a polynomial consisting of exactly two terms?",
                    "options": [],
                    "key": "Binomial",
                    "pos": 4.0,
                    "neg": 1.0,
                    "part": 0.0,
                },
            ],
            "Physics": [
                {
                    "type": QuestionType.MCQ_SINGLE,
                    "prompt": r"Which SI unit is used to measure electrical charge?",
                    "options": [
                        ("A", "Volt (V)", False),
                        ("B", "Ohm (Ω)", False),
                        ("C", "Coulomb (C)", True),
                        ("D", "Watt (W)", False),
                    ],
                    "key": "C",
                    "pos": 4.0,
                    "neg": 1.0,
                    "part": 0.0,
                },
                {
                    "type": QuestionType.MCQ_MULTI,
                    "prompt": r"Select all vector quantities from the following list:",
                    "options": [
                        ("A", "Velocity", True),
                        ("B", "Mass", False),
                        ("C", "Acceleration", True),
                        ("D", "Temperature", False),
                    ],
                    "key": "A,C",
                    "pos": 4.0,
                    "neg": 1.0,
                    "part": 2.0,
                },
                {
                    "type": QuestionType.NUMERICAL,
                    "prompt": r"Calculate the kinetic energy in joules ($E_k = \frac{1}{2}mv^2$) of a $2\text{ kg}$ object moving at $3\text{ m/s}$.",
                    "options": [],
                    "key": "9",
                    "min": 8.9,
                    "max": 9.1,
                    "pos": 4.0,
                    "neg": 0.0,
                    "part": 0.0,
                },
                {
                    "type": QuestionType.ONE_WORD,
                    "prompt": r"What is the SI unit of electrical resistance?",
                    "options": [],
                    "key": "Ohm",
                    "pos": 4.0,
                    "neg": 1.0,
                    "part": 0.0,
                },
            ],
            "Chemistry": [
                {
                    "type": QuestionType.MCQ_SINGLE,
                    "prompt": r"What is the hybridization of carbon in a methane ($\text{CH}_4$) molecule?",
                    "options": [
                        ("A", r"$sp$", False),
                        ("B", r"$sp^2$", False),
                        ("C", r"$sp^3$", True),
                        ("D", r"$dsp^2$", False),
                    ],
                    "key": "C",
                    "pos": 4.0,
                    "neg": 1.0,
                    "part": 0.0,
                },
                {
                    "type": QuestionType.MCQ_MULTI,
                    "prompt": r"Select all noble gases from the list below:",
                    "options": [
                        ("A", "Neon", True),
                        ("B", "Oxygen", False),
                        ("C", "Argon", True),
                        ("D", "Nitrogen", False),
                    ],
                    "key": "A,C",
                    "pos": 4.0,
                    "neg": 1.0,
                    "part": 2.0,
                },
                {
                    "type": QuestionType.NUMERICAL,
                    "prompt": r"What is the atomic number (number of protons) of a neutral Sodium ($\text{Na}$) atom?",
                    "options": [],
                    "key": "11",
                    "min": 10.9,
                    "max": 11.1,
                    "pos": 4.0,
                    "neg": 0.0,
                    "part": 0.0,
                },
                {
                    "type": QuestionType.ONE_WORD,
                    "prompt": r"What is the standard chemical symbol for Gold?",
                    "options": [],
                    "key": "Au",
                    "pos": 4.0,
                    "neg": 1.0,
                    "part": 0.0,
                },
            ],
            "General Aptitude": [
                {
                    "type": QuestionType.MCQ_SINGLE,
                    "prompt": r"If all Bloops are Razzies and all Razzies are Lazzies, then all Bloops are definitely:",
                    "options": [
                        ("A", "Lazzies", True),
                        ("B", "Razzies only", False),
                        ("C", "Not Lazzies", False),
                        ("D", "None of the above", False),
                    ],
                    "key": "A",
                    "pos": 4.0,
                    "neg": 1.0,
                    "part": 0.0,
                },
                {
                    "type": QuestionType.MCQ_MULTI,
                    "prompt": r"Which of the following numbers are prime numbers?",
                    "options": [
                        ("A", "2", True),
                        ("B", "4", False),
                        ("C", "7", True),
                        ("D", "9", False),
                    ],
                    "key": "A,C",
                    "pos": 4.0,
                    "neg": 1.0,
                    "part": 2.0,
                },
                {
                    "type": QuestionType.NUMERICAL,
                    "prompt": r"Find the next number in the geometric sequence: $2, 4, 8, 16, ?$ :",
                    "options": [],
                    "key": "32",
                    "min": 31.9,
                    "max": 32.1,
                    "pos": 4.0,
                    "neg": 0.0,
                    "part": 0.0,
                },
                {
                    "type": QuestionType.ONE_WORD,
                    "prompt": r"What is the capital city of France?",
                    "options": [],
                    "key": "Paris",
                    "pos": 4.0,
                    "neg": 1.0,
                    "part": 0.0,
                },
            ],
        }

        created_questions = []
        global_q_num = 1

        for sec_order, (sec_name, q_list) in enumerate(subject_data.items(), start=1):
            sec, _ = Section.all_objects.update_or_create(
                organization=org_ezexam,
                question_bank=qbank,
                name=sec_name,
                defaults={"order": sec_order},
            )
            for q_info in q_list:
                q, _ = Question.objects.update_or_create(
                    question_bank=qbank,
                    question_number=global_q_num,
                    defaults={
                        "section": sec,
                        "section_name": sec_name,
                        "question_type": q_info["type"],
                        "content_text": q_info["prompt"],
                        "key": q_info["key"],
                        "positive_marks": q_info["pos"],
                        "negative_marks": q_info["neg"],
                        "partial_marks": q_info["part"],
                        "numerical_min": q_info.get("min"),
                        "numerical_max": q_info.get("max"),
                    },
                )
                for opt_idx, (okey, otext, is_c) in enumerate(q_info.get("options", []), start=1):
                    Option.objects.update_or_create(
                        question=q,
                        option_key=okey,
                        defaults={
                            "content_text": otext,
                            "is_correct": is_c,
                            "order": opt_idx,
                        },
                    )
                created_questions.append((sec_name, sec_order, q))
                global_q_num += 1

        # 6. Complete Exam Lifecycles: DRAFT, PUBLISHED, ONGOING, EVALUATED
        now = timezone.now()

        # Helper to attach sections and questions to an exam
        def _attach_exam_structure(exam):
            sec_map = {}
            for sname, sorder, question in created_questions:
                if sname not in sec_map:
                    es, _ = ExaminationSection.objects.update_or_create(
                        exam=exam,
                        title=sname,
                        defaults={"order": sorder, "total_questions": 4},
                    )
                    sec_map[sname] = es
                es = sec_map[sname]
                ExaminationQuestion.objects.update_or_create(
                    exam_section=es,
                    question=question,
                    defaults={"order": question.question_number},
                )

        # Lifecycle 1: DRAFT
        exam_draft, _ = Examination.all_objects.update_or_create(
            organization=org_ezexam,
            code="EXAM-DRAFT-01",
            defaults={
                "name": "Class 12 - Periodic Assessment (Draft)",
                "status": ExaminationStatus.DRAFT,
                "duration_minutes": 60,
                "total_marks": Decimal("64.00"),
                "question_paper": qbank,
                "created_by": faculty,
                "start_window": now + timedelta(days=14),
                "end_window": now + timedelta(days=21),
            },
        )
        _attach_exam_structure(exam_draft)

        # Lifecycle 2: PUBLISHED
        exam_pub, _ = Examination.all_objects.update_or_create(
            organization=org_ezexam,
            code="EXAM-PUB-01",
            defaults={
                "name": "Class 12 - National Benchmark Exam 2026",
                "status": ExaminationStatus.PUBLISHED,
                "duration_minutes": 90,
                "total_marks": Decimal("64.00"),
                "question_paper": qbank,
                "created_by": faculty,
                "start_window": now - timedelta(hours=1),
                "end_window": now + timedelta(days=7),
            },
        )
        _attach_exam_structure(exam_pub)
        CandidateAssignment.objects.get_or_create(exam=exam_pub, batch=batch_eng)
        CandidateAssignment.objects.get_or_create(exam=exam_pub, batch=batch_med)

        # Lifecycle 3: ONGOING (with sample attempts demonstrating all 5 NTA palette states)
        exam_ongoing, _ = Examination.all_objects.update_or_create(
            organization=org_ezexam,
            code="EXAM-LIVE-01",
            defaults={
                "name": "Class 12 - Live Diagnostic CBT Test",
                "status": ExaminationStatus.PUBLISHED,
                "duration_minutes": 60,
                "total_marks": Decimal("64.00"),
                "question_paper": qbank,
                "created_by": faculty,
                "start_window": now - timedelta(minutes=20),
                "end_window": now + timedelta(hours=2),
            },
        )
        _attach_exam_structure(exam_ongoing)
        CandidateAssignment.objects.get_or_create(exam=exam_ongoing, batch=batch_eng)

        # Populate sample in-progress attempt for candidate1 across all 5 NTA palette states
        ongoing_attempt, _ = ExaminationAttempt.objects.update_or_create(
            user=student_users[1],
            examination=exam_ongoing,
            defaults={
                "started_at": now - timedelta(minutes=15),
                "server_deadline": now + timedelta(minutes=45),
                "status": AttemptStatus.IN_PROGRESS,
                "tab_switch_count": 1,
            },
        )

        palette_samples = [
            (created_questions[0][2], ResponseStatus.NOT_VISITED, [], None, 0),
            (created_questions[1][2], ResponseStatus.UNANSWERED, [], None, 25),
            (created_questions[2][2], ResponseStatus.ANSWERED, [], "55", 45),
            (created_questions[3][2], ResponseStatus.MARKED_FOR_REVIEW, [], None, 30),
            (created_questions[4][2], ResponseStatus.ANSWERED_AND_MARKED, ["C"], None, 60),
        ]
        for q, r_status, sel_opts, num_val, t_spent in palette_samples:
            AttemptResponse.objects.update_or_create(
                attempt=ongoing_attempt,
                question=q,
                defaults={
                    "status": r_status,
                    "selected_options": sel_opts,
                    "numerical_value": num_val,
                    "time_spent_seconds": t_spent,
                },
            )

        # Lifecycle 4: EVALUATED
        exam_eval, _ = Examination.all_objects.update_or_create(
            organization=org_ezexam,
            code="EXAM-EVAL-01",
            defaults={
                "name": "All-India Engineering Preliminary Assessment",
                "status": ExaminationStatus.EVALUATED,
                "duration_minutes": 60,
                "total_marks": Decimal("64.00"),
                "question_paper": qbank,
                "created_by": faculty,
                "start_window": now - timedelta(days=5),
                "end_window": now - timedelta(days=2),
            },
        )
        _attach_exam_structure(exam_eval)
        CandidateAssignment.objects.get_or_create(exam=exam_eval, batch=batch_eng)

        # Seed evaluated completed attempts for 10 candidates with varied answers
        for idx in range(1, 11):
            stu = student_users[idx]
            eval_attempt, _ = ExaminationAttempt.objects.update_or_create(
                user=stu,
                examination=exam_eval,
                defaults={
                    "started_at": now - timedelta(days=4, hours=idx),
                    "server_deadline": now - timedelta(days=4, hours=idx - 1),
                    "submitted_at": now - timedelta(days=4, hours=idx - 1, minutes=10),
                    "status": AttemptStatus.SUBMITTED,
                },
            )
            # Answer questions deterministically based on candidate index
            for q_idx, (_, _, q) in enumerate(created_questions):
                # High-performing candidates answer correctly, lower ones make some mistakes
                is_correct = (idx + q_idx) % 3 != 0
                sel = []
                num = None
                if q.question_type == QuestionType.MCQ_SINGLE:
                    sel = [q.key] if is_correct else ["B" if q.key != "B" else "D"]
                elif q.question_type == QuestionType.MCQ_MULTI:
                    sel = q.key.split(",") if is_correct else [q.key.split(",")[0]]
                elif q.question_type == QuestionType.NUMERICAL:
                    num = q.key if is_correct else "999"
                elif q.question_type == QuestionType.ONE_WORD:
                    num = q.key if is_correct else "Incorrect"

                AttemptResponse.objects.update_or_create(
                    attempt=eval_attempt,
                    question=q,
                    defaults={
                        "status": ResponseStatus.ANSWERED,
                        "selected_options": sel,
                        "numerical_value": num,
                        "time_spent_seconds": 30 + idx * 2,
                    },
                )

        # Run automated evaluation to generate scorecards, percentiles, rankings, and question reviews
        evaluate_examination(exam_eval.id)
        Result.objects.filter(attempt__examination=exam_eval).update(is_published=True)

        self.stdout.write(self.style.SUCCESS("✓ Seeded Organizations: Exam-Kraft Academy, Apex Technical Institute"))
        self.stdout.write(self.style.SUCCESS(f"✓ Seeded Accounts: SuperAdmin, OrgAdmin, Faculty, {len(student_users)} Students"))
        self.stdout.write(self.style.SUCCESS("✓ Seeded Master Data: Batches (ENG-12A, MED-12B), Centers (CENTER-MAIN, CENTER-NORTH)"))
        self.stdout.write(self.style.SUCCESS("✓ Seeded Question Bank: 16 questions across Math, Physics, Chemistry, Aptitude"))
        self.stdout.write(self.style.SUCCESS("✓ Seeded Exam Lifecycles: DRAFT, PUBLISHED, ONGOING (5 NTA palette states), EVALUATED (with scored percentiles & rankings)"))
        self.stdout.write(self.style.SUCCESS(f"✓ Published Exam ID: {exam_pub.id}"))
        self.stdout.write(self.style.SUCCESS(f"✓ Live Ongoing Exam ID: {exam_ongoing.id}"))
        self.stdout.write(self.style.SUCCESS(f"✓ Evaluated Exam ID: {exam_eval.id}"))
