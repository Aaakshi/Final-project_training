def bulk_upload(
    files: List[UploadFile] = File(...),
    batch_name: str = Form(...),
    target_department: str = Form(...),
    current_user: dict = Depends(get_current_user)
):
    """Upload multiple documents for classification and routing"""
    if not files:
        raise HTTPException(status_code=400, detail="No files provided")

    if not target_department:
        raise HTTPException(status_code=400, detail="Target department is required")

    batch_id = str(uuid.uuid4())
    uploaded_files = []
    failed_files = []

    # Create batch record
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute('''
        INSERT INTO upload_batches (batch_id, user_id, batch_name, total_files, created_at)
        VALUES (?, ?, ?, ?, ?)
    ''', (batch_id, current_user['user_id'], batch_name, len(files), datetime.datetime.utcnow().isoformat()))

    # Create uploads directory if it doesn't exist
    upload_dir = Path("uploads") / batch_id
    upload_dir.mkdir(parents=True, exist_ok=True)

    for file in files:
        try:
            # Validate file
            if file.size > 10 * 1024 * 1024:  # 10MB limit
                failed_files.append(f"{file.filename}: File too large")
                continue

            # Save file
            file_path = upload_dir / secure_filename(file.filename)
            with open(file_path, "wb") as buffer:
                content = await file.read()
                buffer.write(content)

            # Extract text content
            extracted_text = ""
            try:
                if file.filename.lower().endswith('.pdf'):
                    with open(file_path, 'rb') as pdf_file:
                        pdf_reader = PyPDF2.PdfReader(pdf_file)
                        for page in pdf_reader.pages:
                            extracted_text += page.extract_text()
                elif file.filename.lower().endswith('.txt'):
                    with open(file_path, 'r', encoding='utf-8') as txt_file:
                        extracted_text = txt_file.read()
                elif file.filename.lower().endswith('.docx'):
                    doc = docx.Document(file_path)
                    extracted_text = '\n'.join([paragraph.text for paragraph in doc.paragraphs])
            except Exception as e:
                print(f"Text extraction failed for {file.filename}: {e}")
                extracted_text = f"Text extraction failed: {str(e)}"

            # Simulate classification
            doc_type = "general_document"
            priority = "medium"
            if "invoice" in file.filename.lower() or "receipt" in file.filename.lower():
                doc_type = "financial_document"
                priority = "high"
            elif "contract" in file.filename.lower() or "legal" in file.filename.lower():
                doc_type = "legal_document"
                priority = "high"
            elif "hr" in file.filename.lower() or "employee" in file.filename.lower():
                doc_type = "hr_document"
                priority = "medium"

            # Create document record
            doc_id = str(uuid.uuid4())
            cursor.execute('''
                INSERT INTO documents (
                    doc_id, user_id, original_name, file_path, file_size, file_type, 
                    mime_type, uploaded_at, processing_status, extracted_text, 
                    document_type, department, priority, classification_confidence,
                    page_count, language, tags, review_status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                doc_id, current_user['user_id'], file.filename, str(file_path), 
                file.size, file.filename.split('.')[-1].lower(),
                file.content_type or 'application/octet-stream',
                datetime.datetime.utcnow().isoformat(), "classified", extracted_text,
                doc_type, target_department, priority, 0.85, 1, 'en',
                f'["{doc_type}", "{target_department}"]', "pending"
            ))

            uploaded_files.append({
                'doc_id': doc_id,
                'filename': file.filename,
                'department': target_department,
                'type': doc_type,
                'priority': priority
            })

        except Exception as e:
            failed_files.append(f"{file.filename}: {str(e)}")

    # Update batch status
    cursor.execute('''
        UPDATE upload_batches 
        SET processed_files = ?, failed_files = ?, status = ?, completed_at = ?
        WHERE batch_id = ?
    ''', (len(uploaded_files), len(failed_files), 'completed', 
          datetime.datetime.utcnow().isoformat(), batch_id))

    conn.commit()
    conn.close()

    # Send notifications to department managers
    if uploaded_files:
        # Get department manager emails
        dept_manager_emails = {
            'hr': 'hr.manager@company.com',
            'finance': 'finance.manager@company.com',
            'legal': 'legal.manager@company.com',
            'sales': 'sales.manager@company.com',
            'marketing': 'marketing.manager@company.com',
            'it': 'it.manager@company.com',
            'operations': 'operations.manager@company.com',
            'support': 'support.manager@company.com',
            'procurement': 'procurement.manager@company.com',
            'product': 'product.manager@company.com',
            'administration': 'administration.manager@company.com',
            'executive': 'executive.manager@company.com'
        }

        manager_email = dept_manager_emails.get(target_department, 'admin@company.com')

        # Send notification email to department manager
        subject = f"New Documents Uploaded to {target_department.upper()} Department"
        body = f"""
        <html>
            <body>
                <h2>New Documents Uploaded for Review</h2>
                <p>Dear Department Manager,</p>
                <p>{current_user['full_name']} has uploaded {len(uploaded_files)} document(s) to the {target_department.upper()} department.</p>

                <h3>Documents:</h3>
                <ul>
        """

        for doc in uploaded_files:
            body += f"""
                    <li>
                        <strong>{doc['filename']}</strong><br>
                        Type: {doc['type']}<br>
                        Priority: {doc['priority']}<br>
                        Department: {doc['department'].upper()}
                    </li>
            """

        body += """
                </ul>
                <p>Please review these documents in the IDCR system.</p>
                <p>Best regards,<br>IDCR System</p>
            </body>
        </html>
        """

        send_email(manager_email, subject, body, None, None, current_user['email'])

        # Send confirmation email to uploader
        confirmation_subject = f"Document Upload Confirmation - {len(uploaded_files)} files processed"
        confirmation_body = f"""
        <html>
            <body>
                <h2>Upload Successful</h2>
                <p>Dear {current_user['full_name']},</p>
                <p>Your {len(uploaded_files)} document(s) have been successfully uploaded and sent to the {target_department.upper()} department for review.</p>
                <p>You will receive another notification once the documents are reviewed.</p>
                <p>Best regards,<br>IDCR System</p>
            </body>
        </html>
        """

        send_email(current_user['email'], confirmation_subject, confirmation_body, None, None, "noreply@idcr-system.com")

    return {
        "batch_id": batch_id,
        "message": f"Successfully uploaded {len(uploaded_files)} files to {target_department} department",
        "total_files": len(uploaded_files),
        "failed_files": failed_files if failed_files else None
    }

if __name__ == "__main__":
    init_database()
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=False)