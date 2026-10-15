# 🌱 AgriVault – Agricultural Knowledge and Policy Repository

AgriVault is a web-based application designed to help users access agricultural knowledge, farming practices, pest management information, and government policies in one place.

The system includes an NLP-based query-answering feature that helps users find relevant agricultural articles based on their questions.

## ✨ Features

- **User Authentication** – User registration and login.
- **Agricultural Articles** – Access articles on farming and agricultural practices.
- **Pest Management** – Explore information related to pest control and management.
- **Government Policies** – View agricultural schemes, policies, eligibility criteria, benefits, and official links.
- **NLP-Based Query Answering** – Find relevant articles using TF-IDF and cosine similarity.
- **Admin Dashboard** – Manage agricultural articles and government policy information.
- **File Uploads** – Support for article images and PDF documents.

## 🛠️ Technologies Used

- **Frontend:** HTML5, CSS3, Bootstrap 5, JavaScript
- **Backend:** Python, Flask
- **Database:** MySQL
- **NLP:** TF-IDF and Cosine Similarity
- **Development Tools:** Visual Studio Code, MySQL Workbench

## 📂 Project Structure

```text
AgriVault/
├── app.py
├── templates/
├── static/
│   └── uploads/
├── README.md
└── requirements.txt
```

*Note: The structure shown above is a simplified overview.*

## ⚙️ Installation and Setup

### 1. Clone the repository

```bash
git clone YOUR_GITHUB_REPOSITORY_URL
cd AgriVault
```

### 2. Create a virtual environment

```bash
python -m venv venv
```

### 3. Activate the virtual environment

**Windows PowerShell:**

```powershell
.\venv\Scripts\Activate.ps1
```

### 4. Install dependencies

```bash
pip install -r requirements.txt
```

### 5. Configure the database

- Create a MySQL database named `agrivault_db`.
- Create the required tables using the project's database schema.
- Configure the database connection settings securely using environment variables.

### 6. Run the application

```bash
python app.py
```

Open `http://127.0.0.1:5000` in your browser.

## 🔐 Security Note

Do not upload database passwords, secret keys, `.env` files, or other sensitive credentials to GitHub.

## 🎯 Project Objective

The main objective of AgriVault is to provide a centralized platform for agricultural knowledge and government policy information, with NLP-based retrieval to make relevant information easier to find.

## 👩‍💻 Academic Project

Developed as part of the Master of Computer Applications (MCA) program.
