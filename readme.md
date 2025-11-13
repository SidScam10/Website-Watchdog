# Website Watchdog

Website Watchdog is a serverless application designed to monitor website uptime and analyze public sentiment from Twitter. It features a web-based dashboard for users to add, manage, and view the status of monitored websites.

The application is built using AWS SAM and includes:
* A static HTML/JavaScript frontend with AWS Cognito for authentication.
* An AWS API Gateway.
* Two Python-based AWS Lambda functions for backend logic.
* An Amazon DynamoDB table for data storage.
* An Amazon SNS topic for alerts.

There are two main branches present in the repo: main and AWS-Branch, where the main branch deals with local deployment and AWS-Branch deals with the specific configuration and changes to suit production code deployed onto AWS services.

You can visit the deployed Website-Watchdog using the release URL.

## **WARNING:** 
The Twitter Bearer Token is limited to only Free-Tier Use and is automatically scheduled to fetch and run tweets weekly once to align with free tier limitations of the project
**DO NOT** keep requesting checks as API limits will be exhausted and there is a rate limit of 15 mins per 10 posts check.

## Prerequisites

Before you begin, you must have the following tools installed and configured:

* **AWS CLI:** Installed and configured with your AWS credentials.
* **AWS SAM CLI:** The core tool for running the serverless backend locally.
* **Docker:** Required by the SAM CLI to simulate Lambda and DynamoDB. Docker must be running.
* **Python 3.13:** As specified in `template.yaml`.
* **A Twitter Developer Account:** You must have a developer account with v2 API access to generate a **Bearer Token**.

## Step 1: Configure AWS Resources

This project, even when run locally, depends on cloud resources that must be created in your AWS account first.

1.  **Amazon Cognito:** The frontend (`index.html`) is hardcoded to use an existing Cognito User Pool and App Client. You must create your own and update these values in `index.html`:
    * `userPoolId`
    * `clientId`
    * `cognitoDomain`
    * (The `authority` in `authSettings` will also need to be updated).

2.  **Amazon SNS:** The `template.yaml` defines an SNS topic (`WebsiteWatchdogAlerts`) with a hardcoded email. You should update this to your own email address and **confirm the subscription** in your email inbox.

## Step 2: Configure Local Environment

1.  **Clone the Repository:**
    ```bash
    git clone https://github.com/SidScam10/Website-Watchdog
    cd Website-Watchdog
    ```

2.  **Create Python Dependencies:**
    The SAM build requires `requirements.txt` files for each Lambda function. Create the following two files:

    * `data_api_lambda/requirements.txt`:
        ```
        boto3
        ```

    * `uptime_checker_lambda/requirements.txt`:
        ```
        boto3
        requests
        tweepy
        textblob
        ```

3.  **Create Environment Variables File:**
    SAM uses an environment variable file to pass secrets and configuration to the local Lambda containers. Create a file named `env.json` in the root of the project:

    * `env.json`:
        ```json
        {
          "DataApiFunction": {
            "DYNAMODB_TABLE": "WebsitesTable"
          },
          "UptimeCheckerFunction": {
            "DYNAMODB_TABLE": "WebsitesTable",
            "SNS_TOPIC_ARN": "[Your-SNS-Topic-ARN-From-Step-1]",
            "TWITTER_BEARER_TOKEN": "[Your-Twitter-Bearer-Token]"
          }
        }
        ```
    Replace the bracketed values with your actual ARN and Token. You can find the SNS Topic ARN in the AWS console.

## Step 3: Running the Local Backend

The backend consists of the local API Gateway and the local DynamoDB database.

1.  **Start Local DynamoDB:**
    Open a terminal and run the following Docker command to start a local DynamoDB instance:
    ```bash
    docker run -p 8000:8000 amazon/dynamodb-local
    ```
    (Note: The Python code connects to `http://host.docker.internal:8000`, which is the correct way for a container to reach the host machine. The command above exposes port 8000 on your host.)

2.  **Create the DynamoDB Table:**
    Open a **second terminal**. Run this command to create the `WebsitesTable` in your local DynamoDB instance.
    ```bash
    aws dynamodb create-table \
        --table-name WebsitesTable \
        --attribute-definitions AttributeName=website_url,AttributeType=S \
        --key-schema AttributeName=website_url,KeyType=HASH \
        --provisioned-throughput ReadCapacityUnits=1,WriteCapacityUnits=1 \
        --endpoint-url http://localhost:8000
    ```

3.  **Build the SAM Application:**
    In the same terminal, build the Lambda functions:
    ```bash
    sam build
    ```

4.  **Start the Local API:**
    Finally, start the local SAM API. This command simulates API Gateway and hosts your Lambda functions.
    ```bash
    sam local start-api --env-vars env.json
    ```
    Your backend API is now running at `http://127.0.0.1:3000`.

## Step 4: Running the Local Frontend

1.  **Update Frontend Configuration:**
    Open `index.html` and ensure the `cognitoConfig` section is correct:
    * Verify all Cognito values match the pool you created in Step 1.
    * `apiGatewayEndpoint`: Must be `'http://127.0.0.1:3000'`
    * `redirectUri`: Must be `'http://localhost:8081'`
    * `logoutUri`: Must be `'http://localhost:8081'`

2.  **Serve the Frontend:**
    The `index.html` file must be served from a web server. You can use Python's built-in server. Open a **third terminal** in the project's root directory:
    ```bash
    python -m http.server 8081
    ```

## Step 5: Using the Application

1.  Open your web browser and navigate to `http://localhost:8081`.
2.  Click the "Cognito Sign In" button.
3.  Log in through your Cognito hosted UI.
4.  After being redirected back, you will see the dashboard.
5.  Use the form to add a website URL (e.g., `https://google.com`) and a Twitter keyword (e.g., `#google`).
6.  The site will be added to your DynamoDB table and appear in the "Monitored Services" list.

### Triggering the Uptime Checker Locally

The `UptimeCheckerFunction` is designed to run on a schedule, which `sam local` does not simulate. To test it, you must trigger it manually.

You can do this in two ways:

1.  **Via the UI:** Click the "Request Check" button on a website card. This calls the `/request-check` API endpoint, which invokes the `UptimeCheckerFunction` and sends an SNS notification to the admin.
2.  **Via the SAM CLI:** To simulate the scheduled event that checks *all* websites, run the following command in your second terminal (where you ran `sam build`):
    ```bash
    sam local invoke UptimeCheckerFunction --env-vars env.json
    ```
    After the function runs, refresh the dashboard to see the updated status and sentiment scores.