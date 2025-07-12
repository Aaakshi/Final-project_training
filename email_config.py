
# Email Configuration for IDCR System
# Configure these settings for your Outlook email account

# IMPORTANT: To use this with Outlook, you need to:
# 1. Enable 2-factor authentication on your Microsoft account
# 2. Generate an "App Password" specifically for this application
# 3. Use the app password instead of your regular password

EMAIL_CONFIG = {
    # Outlook SMTP settings
    "SMTP_SERVER": "smtp-mail.outlook.com",
    "SMTP_PORT": 587,
    
    # Your Outlook email credentials
    "EMAIL_USER": "your-email@outlook.com",  # Replace with your actual Outlook email
    "EMAIL_PASSWORD": "your-app-password",   # Replace with your Outlook app password
    
    # Email templates
    "FROM_NAME": "IDCR System",
    
    # Department email addresses (customize these for your organization)
    "DEPARTMENT_EMAILS": {
        "finance": "finance@your-company.com",
        "legal": "legal@your-company.com", 
        "hr": "hr@your-company.com",
        "it": "it@your-company.com",
        "general": "general@your-company.com"
    }
}

# Instructions for setting up Outlook app password:
"""
1. Go to https://account.microsoft.com/security
2. Sign in with your Microsoft account
3. Select "Security dashboard"
4. Select "Advanced security options"
5. Under "App passwords", select "Create a new app password"
6. Follow the instructions to get your app password
7. Use this app password in the EMAIL_PASSWORD field above
"""
