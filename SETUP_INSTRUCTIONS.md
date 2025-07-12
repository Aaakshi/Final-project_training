
# IDCR System Setup Instructions

## Enhanced Features Added

✅ **User Authentication System**
- User registration and login
- JWT-based authentication
- Role-based access control (employee, manager, admin)

✅ **Complete Document Workflow**
- Automatic document classification
- Department-based routing
- Real-time status tracking
- Email notifications

✅ **Email Integration**
- Outlook SMTP integration
- Automatic notifications to departments
- Approval/rejection notifications to users

## Setup Instructions

### 1. Email Configuration

1. **Set up your Outlook account for app passwords:**
   - Go to https://account.microsoft.com/security
   - Enable 2-factor authentication
   - Generate an "App Password" for this application

2. **Configure email settings:**
   - Open `email_config.py`
   - Replace `your-email@outlook.com` with your actual Outlook email
   - Replace `your-app-password` with your generated app password
   - Update department email addresses for your organization

### 2. Security Configuration

1. **Update the secret key in main.py:**
   ```python
   SECRET_KEY = "your-very-secure-secret-key-here"  # Change this to a secure random string
   ```

### 3. Department Configuration

Update the default departments in the database initialization or add your own departments through the admin interface.

## User Workflow

### For Employees:
1. **Register** an account with email and department
2. **Upload documents** in batches with descriptive names
3. **Track status** - documents go through: uploaded → processing → classified → reviewed
4. **Receive email notifications** when documents are approved/rejected

### For Department Managers:
1. **Receive email notifications** when new documents are uploaded to their department
2. **Review documents** through the web interface
3. **Approve or reject** documents with optional comments
4. **Users get automatic email notifications** of the decision

### Document Processing Flow:
```
Upload → Classification → Department Routing → Email to Department → Review → Email to User
```

## Features

### 🔐 Authentication
- Secure JWT-based authentication
- User registration with email verification
- Role-based access control

### 📄 Document Management
- Bulk upload (up to 50 files)
- Automatic classification using AI
- Real-time processing status
- Advanced filtering and search

### 📧 Email Notifications
- Welcome emails for new users
- Department notifications for new documents
- Approval/rejection notifications
- Outlook SMTP integration

### 📊 Dashboard
- Real-time statistics
- Document status tracking
- User-specific views based on role
- Responsive design

### 🔄 Workflow Integration
- Automatic department routing
- Review and approval process
- Status tracking throughout the pipeline
- Email notifications at each step

## API Endpoints

### Authentication
- `POST /api/register` - User registration
- `POST /api/login` - User login
- `GET /api/me` - Get current user info

### Documents
- `POST /api/bulk-upload` - Upload documents
- `GET /api/documents` - List documents with filters
- `GET /api/documents/{id}` - Get document details
- `POST /api/documents/{id}/review` - Review document

### Statistics
- `GET /api/stats` - Get dashboard statistics
- `GET /api/health` - Service health check

## Technical Stack

- **Backend**: FastAPI, SQLite, JWT authentication
- **Frontend**: HTML, CSS, JavaScript (Vanilla)
- **Email**: SMTP with Outlook
- **File Processing**: PyPDF2, python-docx, pytesseract
- **AI Services**: Microservices architecture

## Security Features

- JWT token-based authentication
- Password hashing
- Input validation
- File type and size restrictions
- Role-based access control
- Secure email configuration

## Running the Application

1. **Install dependencies:**
   ```bash
   pip install PyJWT python-multipart
   ```

2. **Configure email settings** in `email_config.py`

3. **Start the application:**
   ```bash
   python main.py
   ```

4. **Access the application:**
   - Open http://0.0.0.0:5000 in your browser
   - Register a new account or login
   - Start uploading and managing documents!

## Troubleshooting

### Email Issues
- Ensure 2-factor authentication is enabled on your Microsoft account
- Use an app password, not your regular password
- Check that the email addresses in `email_config.py` are correct

### Authentication Issues
- Check that the SECRET_KEY is properly set
- Ensure JWT tokens are being sent in the Authorization header

### File Upload Issues
- Check file size limits (10MB per file, 50 files max)
- Ensure supported file types (PDF, DOCX, TXT, XLSX, images)
- Verify sufficient disk space for uploads

For more help, check the console logs for detailed error messages.
