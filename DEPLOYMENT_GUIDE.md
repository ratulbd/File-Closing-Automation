# Employee Clearance System - Deployment Guide

## Overview
This guide explains how to deploy the Employee Clearance System using:
1. **Google Sheets** as the database (free)
2. **Firebase Hosting** for the frontend (free)
3. **Python backend** (deploy on free services like Render, Railway, or PythonAnywhere)

## Prerequisites
- Google account (for Google Sheets API)
- Firebase account (for hosting)
- GitHub account (optional, for deployment)

---

## Part 1: Google Sheets Setup

### 1.1 Create Google Cloud Project
1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project (e.g., "Employee-Clearance-System")
3. Enable Google Sheets API:
   - Navigate to "APIs & Services" > "Library"
   - Search for "Google Sheets API" and enable it

### 1.2 Create Service Account
1. Go to "APIs & Services" > "Credentials"
2. Click "Create Credentials" > "Service Account"
3. Fill in details:
   - Name: `employee-clearance-sa`
   - Role: `Editor` (or create custom role with Sheets permissions)
4. Click "Create Key" > "JSON" and download the key file
5. Save it as `credentials.json` in the `backend/` directory

### 1.3 Create Google Spreadsheet
1. Create a new Google Sheet at [sheets.google.com](https://sheets.google.com)
2. Name it "Employee Clearance System"
3. Share the spreadsheet with your service account email (found in credentials.json)
   - Click "Share" button
   - Add service account email with "Editor" permission
4. Get the Spreadsheet ID from the URL:
   - URL format: `https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/edit`
   - Copy the `SPREADSHEET_ID`

### 1.4 Configure Environment Variables
Create a `.env` file in the `backend/` directory:
```bash
GOOGLE_SHEETS_ID=your_spreadsheet_id_here
GOOGLE_APPLICATION_CREDENTIALS=./credentials.json
SECRET_KEY=your_secret_key_here
ACCESS_TOKEN_EXPIRE_MINUTES=30
```

---

## Part 2: Backend Deployment (Free Options)

### Option A: Render.com (Free Tier)
1. Push code to GitHub repository
2. Go to [Render.com](https://render.com)
3. Create a new "Web Service"
4. Connect your GitHub repository
5. Configure:
   - **Name**: `employee-clearance-backend`
   - **Environment**: `Python 3`
   - **Build Command**: `pip install -r backend/requirements.txt`
   - **Start Command**: `cd backend && uvicorn main_gsheets:app --host 0.0.0.0 --port $PORT`
6. Add environment variables from your `.env` file
7. Deploy

### Option B: Railway.app (Free Tier)
1. Install Railway CLI or use web interface
2. Create new project
3. Add environment variables
4. Deploy from GitHub or upload code

### Option C: PythonAnywhere (Free Tier)
1. Create free account at [PythonAnywhere](https://www.pythonanywhere.com)
2. Upload backend files
3. Create virtual environment and install dependencies
4. Configure web app with Flask/FastAPI
5. Set up environment variables

### Option D: Local with Ngrok (For Testing)
1. Run backend locally:
   ```bash
   cd backend
   python -m uvicorn main_gsheets:app --host 0.0.0.0 --port 8000
   ```
2. Install ngrok: `npm install -g ngrok`
3. Expose localhost:
   ```bash
   ngrok http 8000
   ```
4. Use the ngrok URL as your API endpoint

---

## Part 3: Frontend Deployment (Firebase Hosting)

### 3.1 Install Firebase CLI
```bash
npm install -g firebase-tools
```

### 3.2 Login to Firebase
```bash
firebase login
```

### 3.3 Initialize Firebase in Frontend
```bash
cd frontend
firebase init
```
Select:
- **Hosting**: Configure and deploy Firebase Hosting sites
- **Use existing project** or create new
- **Public directory**: `dist`
- **Single-page app**: Yes
- **Auto-build**: No

### 3.4 Configure API Endpoint
Create `frontend/.env.production`:
```bash
VITE_API_URL=https://your-backend-url.onrender.com
```
Replace with your actual backend URL.

### 3.5 Build and Deploy
```bash
cd frontend
npm run build
firebase deploy
```

### 3.6 Automatic Deployment (Optional)
Add to `package.json` scripts:
```json
"deploy": "npm run build && firebase deploy --only hosting"
```
Then run:
```bash
npm run deploy
```

---

## Part 4: Initial Setup

### 4.1 Initialize Google Sheets
Run the backend once to create default worksheets:
```bash
cd backend
python -c "from google_sheets import get_sheets_service; sheets = get_sheets_service(); sheets.initialize_spreadsheet()"
```

### 4.2 Create Default Users
The system will automatically create default users on first run:
- `hr_telecom@ecp.com` / `password` (HR, Telecom)
- `hr_group@ecp.com` / `password` (HR, Group)
- `it@ecp.com` / `password` (IT)
- `accounts@ecp.com` / `password` (Accounts)
- `audit@ecp.com` / `password` (Audit)
- `finance@ecp.com` / `password` (Finance)

**IMPORTANT**: Change passwords after first login!

---

## Part 5: Testing the System

### 5.1 Test Backend
```bash
curl -X GET https://your-backend-url.onrender.com/health
```
Should return: `{"status":"healthy","database":"google_sheets"}`

### 5.2 Test Frontend
1. Open your Firebase Hosting URL
2. Login with default credentials
3. Create a test clearance file
4. Test workflow steps

### 5.3 Verify Google Sheets
Check your Google Sheet - it should have 4 worksheets:
1. **Users** - User accounts
2. **ClearanceFiles** - Employee clearance files
3. **ClearanceSteps** - Workflow steps
4. **Rejections** - Rejection history

---

## Part 6: Maintenance

### 6.1 Backup Google Sheets
- Google Sheets automatically saves versions
- Use "File > Version history" to restore
- Export as Excel/CSV periodically

### 6.2 Monitor Usage
- **Google Sheets API**: 100 requests per 100 seconds (free quota)
- **Firebase Hosting**: 10GB storage, 360MB/day bandwidth (free tier)
- **Render/Railway**: Check free tier limits

### 6.3 Scaling Considerations
If you exceed free limits:
1. Upgrade Google Cloud to paid tier ($)
2. Use Firebase paid plan for more bandwidth
3. Consider migrating to proper database (PostgreSQL)

---

## Troubleshooting

### Common Issues

1. **Google Sheets API Error**
   - Check service account permissions
   - Verify spreadsheet is shared with service account
   - Check GOOGLE_SHEETS_ID is correct

2. **Backend Won't Start**
   - Check all environment variables are set
   - Verify dependencies are installed
   - Check port configuration

3. **Frontend Can't Connect to Backend**
   - Verify CORS is configured in backend
   - Check VITE_API_URL is correct
   - Test backend health endpoint

4. **Authentication Issues**
   - Check JWT secret key
   - Verify token expiration time
   - Clear browser localStorage and login again

### Support
For issues, check:
- Google Sheets API documentation
- Firebase Hosting documentation
- Render/Railway status pages

---

## Security Notes

1. **Change default passwords** immediately
2. **Rotate JWT secret key** periodically
3. **Limit Google Sheets API key** to specific IPs if possible
4. **Use HTTPS** for all connections
5. **Implement rate limiting** on backend
6. **Regularly audit** Google Sheets access

---

## Cost Summary
- **Google Sheets API**: Free for moderate usage
- **Firebase Hosting**: Free tier (10GB storage, 360MB/day)
- **Backend Hosting**: Free on Render/Railway (with limits)
- **Total Cost**: $0 (within free tier limits)

---

## Next Steps
1. Customize the frontend design
2. Add email notifications
3. Implement advanced reporting
4. Add user registration
5. Create mobile app version

---

*Last Updated: April 2026*