import os
import io
import zipfile
import re
from datetime import datetime
from PIL import Image
from django.conf import settings
from django.core.files.storage import default_storage
from django.db import transaction
import openpyxl
from apps.question_bank.models import QuestionBank, Section, Question, Option, QuestionType, normalize_question_type


def process_and_save_image(image_bytes: bytes, filename: str, paper_id: str, max_dim: int = 1200, webp_quality: int = 80):
    """
    Saves:
    1. Raw original image (lossless/original for high-detail zoom)
    2. Lightweight WebP optimized version (fast loading in CBT palette & question area)
    Returns: (optimized_url, raw_url)
    """
    paper_dir = os.path.join(settings.MEDIA_ROOT, 'questions', str(paper_id))
    os.makedirs(paper_dir, exist_ok=True)

    base_name, ext = os.path.splitext(filename)
    clean_base = re.sub(r'[^a-zA-Z0-9_\-]', '_', base_name)
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
    
    # Save raw original
    raw_filename = f"{clean_base}_{timestamp}_raw{ext.lower()}"
    raw_path = os.path.join(paper_dir, raw_filename)
    with open(raw_path, 'wb') as f:
        f.write(image_bytes)
        
    raw_url = f"{settings.MEDIA_URL}questions/{paper_id}/{raw_filename}"
    
    # Process lightweight webp
    try:
        img = Image.open(io.BytesIO(image_bytes))
        if img.mode in ('RGBA', 'LA') or (img.mode == 'P' and 'transparency' in img.info):
            # Convert RGBA to RGB with white background if needed or keep RGBA in webp
            pass
        else:
            img = img.convert('RGB')
            
        # Resize if dimensions exceed max_dim
        w, h = img.size
        if max(w, h) > max_dim:
            scaling = max_dim / float(max(w, h))
            new_size = (int(w * scaling), int(h * scaling))
            img = img.resize(new_size, Image.Resampling.LANCZOS)
            
        opt_filename = f"{clean_base}_{timestamp}_opt.webp"
        opt_path = os.path.join(paper_dir, opt_filename)
        img.save(opt_path, 'WEBP', quality=webp_quality, method=6)
        opt_url = f"{settings.MEDIA_URL}questions/{paper_id}/{opt_filename}"
    except Exception as e:
        # Fallback to raw URL if image conversion fails
        opt_url = raw_url

    return opt_url, raw_url


def ingest_zip_package(zip_file, question_bank: QuestionBank, user=None, reason='Screenshot / Bulk Import'):
    """
    Ingests a ZIP file containing:
    - Multiple image screenshots (png, jpg, webp) -> converted into questions
    - OR an Excel spreadsheet (questions.xlsx) + images/ directory
    """
    created_questions = []
    errors = []

    with zipfile.ZipFile(zip_file, 'r') as z:
        namelist = z.namelist()
        
        # Check if an excel or csv is present
        spreadsheet_name = next((n for n in namelist if n.endswith('.xlsx') or n.endswith('.csv')), None)
        image_files = [n for n in namelist if not n.startswith('__MACOSX') and not n.endswith('/') and os.path.splitext(n)[1].lower() in ('.png', '.jpg', '.jpeg', '.webp', '.bmp', '.gif')]

        # Natural sort image files by name (e.g. q1.png, q2.png ... q10.png)
        def natural_sort_key(s):
            return [int(text) if text.isdigit() else text.lower() for text in re.split(r'(\d+)', s)]
        image_files.sort(key=natural_sort_key)

        # Mode A: Direct Screenshot-to-Question Ingestion (Pure image dump)
        if not spreadsheet_name and image_files:
            start_num = question_bank.questions.count() + 1
            section, _ = Section.objects.get_or_create(
                question_bank=question_bank,
                name='General',
                defaults={
                    'organization': question_bank.organization,
                    'order': 1
                }
            )

            with transaction.atomic():
                for idx, img_name in enumerate(image_files):
                    img_bytes = z.read(img_name)
                    base_filename = os.path.basename(img_name)
                    opt_url, raw_url = process_and_save_image(img_bytes, base_filename, question_bank.id)
                    
                    q_num = start_num + idx
                    
                    # Try to extract key or type hints from filename if present (e.g., q1_MCQ_B.png)
                    q_type = QuestionType.MCQ_SINGLE
                    key = ''
                    key_match = re.search(r'key[_\-]([A-D0-9\.\-]+)', base_filename, re.IGNORECASE)
                    if key_match:
                        key = key_match.group(1).upper()

                    metadata = {
                        'uploaded_by': user.username if user and user.is_authenticated else 'anonymous',
                        'uploaded_at': datetime.now().isoformat(),
                        'original_filename': base_filename,
                        'reason': reason,
                        'source': 'screenshot_zip_ingest',
                    }

                    q = Question.objects.create(
                        question_bank=question_bank,
                        section=section,
                        section_name='General',
                        question_number=q_num,
                        question_type=q_type,
                        content_text=f"Question {q_num} (See attached diagram/screenshot)",
                        content_html=f'<p><img src="{opt_url}" alt="Question {q_num}" class="cbt-question-img" data-raw="{raw_url}" /></p>',
                        image_url=opt_url,
                        raw_image_url=raw_url,
                        upload_metadata=metadata,
                        key=key,
                        positive_marks=4.0,
                        negative_marks=1.0,
                    )
                    
                    # Default 4 options A, B, C, D for MCQ
                    for opt_key in ('A', 'B', 'C', 'D'):
                        Option.objects.create(
                            question=q,
                            option_key=opt_key,
                            content_text=f"Option {opt_key}",
                            is_correct=(opt_key == key),
                            order=ord(opt_key) - ord('A')
                        )
                    created_questions.append(q)

            return {
                'mode': 'SCREENSHOT_IMAGES',
                'questions_created': len(created_questions),
                'questions': [str(q.id) for q in created_questions],
                'errors': errors
            }

        # Mode B: Excel + Images package
        elif spreadsheet_name:
            wb = openpyxl.load_workbook(io.BytesIO(z.read(spreadsheet_name)), data_only=True)
            sheet = wb.active
            rows = list(sheet.iter_rows(values_only=True))
            if not rows:
                return {'error': 'Spreadsheet in ZIP is empty.'}

            header = [str(cell).strip().lower() if cell else '' for cell in rows[0]]
            col_map = {col: i for i, col in enumerate(header)}

            with transaction.atomic():
                start_num = question_bank.questions.count() + 1
                for r_idx, row in enumerate(rows[1:], start=2):
                    if not any(row):
                        continue
                    
                    def get_val(name, default=''):
                        idx = col_map.get(name.lower())
                        if idx is not None and idx < len(row) and row[idx] is not None:
                            return str(row[idx]).strip()
                        return default

                    q_text = get_val('question text') or get_val('question')
                    if not q_text:
                        continue

                    sec_name = get_val('section', 'General')
                    section, _ = Section.objects.get_or_create(
                        question_bank=question_bank,
                        name=sec_name,
                        defaults={
                            'organization': question_bank.organization,
                            'order': 1
                        }
                    )

                    q_type = normalize_question_type(get_val('question type') or get_val('type', 'MCQ_SINGLE'))
                    q_num = int(get_val('question number', start_num))
                    start_num = max(start_num, q_num + 1)
                    key = get_val('correct key') or get_val('key') or get_val('answer', '')
                    pos_marks = float(get_val('positive marks') or get_val('marks', 4.0))
                    neg_marks = float(get_val('negative marks', 1.0))
                    explanation = get_val('explanation', '')
                    img_ref = get_val('image reference') or get_val('image', '')

                    opt_url = None
                    raw_url = None
                    if img_ref:
                        # Find image in zip
                        matched_img = next((n for n in image_files if os.path.basename(n).lower() == img_ref.lower()), None)
                        if matched_img:
                            img_bytes = z.read(matched_img)
                            opt_url, raw_url = process_and_save_image(img_bytes, os.path.basename(matched_img), question_bank.id)

                    metadata = {
                        'uploaded_by': user.username if user and user.is_authenticated else 'anonymous',
                        'uploaded_at': datetime.now().isoformat(),
                        'spreadsheet': spreadsheet_name,
                        'reason': reason,
                        'source': 'zip_spreadsheet_ingest',
                    }

                    q = Question.objects.create(
                        question_bank=question_bank,
                        section=section,
                        section_name=sec_name,
                        question_number=q_num,
                        question_type=q_type,
                        content_text=q_text,
                        image_url=opt_url,
                        raw_image_url=raw_url,
                        explanation=explanation,
                        upload_metadata=metadata,
                        key=key,
                        positive_marks=pos_marks,
                        negative_marks=neg_marks,
                    )

                    # Ingest options if MCQ
                    if q_type in (QuestionType.MCQ_SINGLE, QuestionType.MCQ_MULTI):
                        for opt_key in ('A', 'B', 'C', 'D'):
                            opt_val = get_val(f'option {opt_key}') or get_val(f'opt {opt_key}')
                            if opt_val:
                                is_corr = opt_key.upper() in [k.strip().upper() for k in key.split(',')]
                                Option.objects.create(
                                    question=q,
                                    option_key=opt_key,
                                    content_text=opt_val,
                                    is_correct=is_corr,
                                    order=ord(opt_key) - ord('A')
                                )
                    created_questions.append(q)

            return {
                'mode': 'SPREADSHEET_WITH_IMAGES',
                'questions_created': len(created_questions),
                'questions': [str(q.id) for q in created_questions],
                'errors': errors
            }

    return {'error': 'ZIP package contains no valid images or spreadsheet.'}
