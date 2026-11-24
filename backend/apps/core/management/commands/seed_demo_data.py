import os
from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import FacultyProfile, User, UserProfile, UserRole
from apps.examinations.models import (
    CandidateAssignment, Examination, ExaminationQuestion, ExaminationSection, ExaminationStatus,
)
from apps.organizations.models import Batch, BatchStream, ExaminationCenter, Organization, StudentBatchEnrollment
from apps.question_bank.models import Option, Question, QuestionBank, QuestionType, Section


PAPER = {
    "Mathematics": [
        ("What is the derivative of sin(x)?", ["cos(x)", "-cos(x)", "sin(x)", "-sin(x)"], "A"),
        ("Select all roots of x² − 9 = 0.", ["-3", "0", "3", "9"], "A,C"),
        ("Find the sum of the first ten positive integers.", [], "55"),
        ("What is the determinant of the 2 × 2 identity matrix?", ["0", "1", "2", "-1"], "B"),
    ],
    "Physics": [
        ("Which SI unit measures electric charge?", ["Volt", "Ohm", "Coulomb", "Watt"], "C"),
        ("Select all vector quantities.", ["Velocity", "Mass", "Acceleration", "Temperature"], "A,C"),
        ("Find the kinetic energy in joules of a 2 kg mass moving at 3 m/s.", [], "9"),
        ("Which quantity is conserved in an isolated inelastic collision?", ["Kinetic energy", "Momentum", "Speed", "Temperature"], "B"),
    ],
    "Chemistry": [
        ("What is the hybridization of carbon in methane?", ["sp", "sp²", "sp³", "dsp²"], "C"),
        ("Select all noble gases.", ["Neon", "Oxygen", "Argon", "Nitrogen"], "A,C"),
        ("How many electrons does a neutral sodium atom have?", [], "11"),
        ("What is the usual oxidation state of oxygen in a peroxide?", ["0", "-2", "+1", "-1"], "D"),
    ],
}


class Command(BaseCommand):
    help = "Seed an isolated demo cohort. Use a fresh exam code for each benchmark."

    def add_arguments(self, parser):
        parser.add_argument("--exam-code", default="DEMO-M5")

    def account(self, username, role, name, organization=None):
        privileged = role == UserRole.SUPERADMIN
        user, created = User.objects.get_or_create(username=username, defaults={
            "email": username, "role": role, "organization": organization,
            "is_staff": privileged, "is_superuser": privileged,
        })
        if (user.role, user.organization_id) != (role, getattr(organization, "pk", None)):
            raise CommandError(f"Existing account conflicts with demo account {username}")
        if created:
            user.set_password(self.password)
            user.save(update_fields=["password"])
        UserProfile.objects.get_or_create(user=user, defaults={"full_name": name})
        return user

    @transaction.atomic
    def handle(self, *args, **options):
        self.password = os.environ.get("DEMO_PASSWORD")
        if not self.password or len(self.password) < 12:
            raise CommandError("Set DEMO_PASSWORD to at least 12 characters.")
        code = options["exam_code"]
        if not code or len(code) > 40:
            raise CommandError("Exam code must contain 1–40 characters.")
        self.account("superadmin@demo.ezexam.example", UserRole.SUPERADMIN, "Demo Platform Admin")
        for slug, name, count in (("demo-apex", "Apex Academy", 110), ("demo-summit", "Summit Academy", 15)):
            org, _ = Organization.objects.get_or_create(slug=slug, defaults={"name": name})
            batch, _ = Batch.all_objects.get_or_create(organization=org, code="JEE-2027", defaults={
                "name": "JEE 2027", "stream": BatchStream.JEE_MAIN,
            })
            center, _ = ExaminationCenter.all_objects.get_or_create(organization=org, code="MAIN", defaults={
                "name": f"{name} Main Campus", "capacity": count,
            })
            domain = f"{slug}.ezexam.example"
            self.account(f"admin@{domain}", UserRole.ORG_ADMIN, f"{name} Administrator", org)
            faculty = self.account(f"faculty@{domain}", UserRole.FACULTY, "Dr. Meera Rao", org)
            profile, _ = FacultyProfile.objects.get_or_create(user=faculty, defaults={
                "department": "Science and Mathematics", "subjects": list(PAPER),
            })
            profile.assigned_batches.add(batch)
            profile.assigned_centers.add(center)
            for number in range(1, count + 1):
                roll = f"{number:03d}"
                student = self.account(f"student{roll}@{domain}", UserRole.STUDENT, f"Candidate {roll}", org)
                StudentBatchEnrollment.objects.get_or_create(batch=batch, roll_number=roll, defaults={
                    "student": student, "center": center,
                })
            self.seed_exams(org, batch, faculty, code)

    def seed_exams(self, org, batch, faculty, code):
        paper, _ = QuestionBank.all_objects.get_or_create(organization=org, name="Demo JEE Practice Paper", defaults={
            "created_by": faculty, "exam_type": "JEE_MAIN",
            "instructions": "Select every correct option for multiple-answer questions.",
        })
        now = timezone.now()
        exams = []
        for suffix, status, start in (
            ("", ExaminationStatus.PUBLISHED, now - timedelta(minutes=1)),
            ("-NEXT", ExaminationStatus.SCHEDULED, now + timedelta(days=8)),
        ):
            exam, _ = Examination.all_objects.update_or_create(organization=org, code=code + suffix, defaults={
                "name": f"JEE Practice Exam ({code}{suffix})", "status": status,
                "start_window": start, "end_window": start + timedelta(days=7),
                "question_paper": paper, "created_by": faculty,
                "total_marks": 4 * sum(map(len, PAPER.values())),
            })
            CandidateAssignment.objects.get_or_create(exam=exam, batch=batch)
            exams.append(exam)

        number = 0
        for order, (subject, items) in enumerate(PAPER.items(), 1):
            section, _ = Section.all_objects.get_or_create(organization=org, question_bank=paper, name=subject,
                                                          defaults={"order": order})
            exam_sections = [
                ExaminationSection.objects.get_or_create(exam=exam, title=subject, defaults={
                    "order": order, "total_questions": len(items),
                })[0] for exam in exams
            ]
            for position, (prompt, choices, key) in enumerate(items, 1):
                number += 1
                kind = QuestionType.NUMERICAL
                if choices:
                    kind = QuestionType.MCQ_MULTI if "," in key else QuestionType.MCQ_SINGLE
                question, _ = Question.objects.get_or_create(question_bank=paper, question_number=number, defaults={
                    "section": section, "section_name": subject, "question_type": kind,
                    "content_text": prompt, "key": key,
                })
                for index, (letter, choice) in enumerate(zip("ABCD", choices), 1):
                    Option.objects.get_or_create(question=question, option_key=letter, defaults={
                        "content_text": choice, "is_correct": letter in key.split(","), "order": index,
                    })
                for exam_section in exam_sections:
                    ExaminationQuestion.objects.get_or_create(exam_section=exam_section, question=question,
                                                             defaults={"order": position})
        self.stdout.write(self.style.SUCCESS(f"{org.slug} published exam ID: {exams[0].pk}"))
