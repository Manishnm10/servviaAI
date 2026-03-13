# FS Installation Guide (Development Environment)

This guide provides detailed steps to set up the ServVia Backend development environment, including both frontend and backend setup.

## Prerequisites

Before proceeding, ensure you have the following installed on your local machine:

- **Git**: For version control.
- **Docker & Docker Compose**: For containerization and managing services.
- **Python 3.8+**: For running Python scripts and managing dependencies.
- **Node.js & npm**: For frontend development with React.
- **PostgreSQL**: For database management.

## Installation

### ServVia Backend Frontend

1. **Clone the repository to your local machine:**

    ```bash
    git clone servvia-backend-frontend
    ```

2. **Navigate to the project directory:**

    ```bash
    cd servvia-backend-frontend
    ```

3. **Install the required dependencies using npm:**

    ```bash
    npm install
    ```

### Configuration

The ServVia Backend React App requires specific environment variables to be set for proper functionality. These variables configure the app's behavior and access to external services.

1. **Set up the environment variables:**

   - Create a `.env` file in the root directory of the project.
   - Open the `.env` file and add the following variables:

    ```bash
    REACT_APP_BASEURL="https://datahubethdev.servvia-backend.co/be/"
    REACT_APP_BASEURL_without_slash="https://datahubethdev.servvia-backend.co/be"
    REACT_APP_BASEURL_without_slash_view_data="http://datahubethdev.servvia-backend.co:"
    REACT_APP_DEV_MODE="true"
    ```

    - If you are running your own ServVia Backend backend, replace the URLs appropriately.
    - Make sure to replace the values with the correct URLs and settings for your environment.

2. **Start the ServVia Backend React App:**

    ```bash
    npm start
    ```

    This command will build the app and start a local development server. Open your browser and visit `http://localhost:3000` to access the application.

### Backend Repository

#### Prerequisites to Run ServVia Backend Backend

1. **Clone the servvia-backend repository:**

    ```bash
    git clone servvia-backend.git
    ```

2. **Set up a PostgreSQL or MySQL database on your local machine:**

    You can either pull a Docker image or install PostgreSQL directly on your system.

    - **Using Docker:**

        ```bash
        docker pull postgres
        docker run -p 5432:5432 postgres:latest
        ```

    - **Or install PostgreSQL locally:**

        Follow the appropriate installation steps for your operating system.

3. **Create a user and database in PostgreSQL:**

    After installing PostgreSQL, create a database and user to be used by ServVia Backend.

4. **Set up SendGrid for email services:**

    - Create a SendGrid account and generate an API key.
    - Verify sender authenticity within SendGrid.

5. **Create an environment file (.env) in the `servvia-backend` directory:**

    Replace the placeholder values appropriately:

    ```bash
    PUBLIC_DOMAIN={BACKEND_URL}
    DATAHUB_NAME=ServVia Backend
    DATAHUB_SITE={BACKEND_URL}
    POSTGRES_DB={DATABASE}
    POSTGRES_USER={DB_USER}
    POSTGRES_PASSWORD={DB_PASSWORD}
    POSTGRES_HOST_AUTH_METHOD=trust
    SENDGRID_API_KEY={SG.SENDGRIDKEY}
    EMAIL_HOST_USER={authorized_sendgrid@domain.org}
    PORT={DB_PORT}
    ```

6. **Install the required Python dependencies:**

    ```bash
    cd servvia-backend
    pip install -r requirements.txt
    ```

7. **Run database migrations:**

    ```bash
    python3 manage.py makemigrations
    python3 manage.py migrate
    ```

8. **Start the Django development server:**

    ```bash
    python3 manage.py runserver 0.0.0.0:8000
    ```

    The backend will be accessible at `http://localhost:8000`.

## Conclusion

You have now set up both the frontend and backend of the ServVia Backend development environment. This setup allows you to work on and test the application locally before deploying it to a production environment.
