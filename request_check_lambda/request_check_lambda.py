import json
import boto3
import os

sns = boto3.client('sns')
IS_SAM_LOCAL = os.environ.get('AWS_SAM_LOCAL')
if IS_SAM_LOCAL:
    print("SAM LOCAL: Running in local mode. SNS will be mocked.")
    sns = None # Don't initialize client if local
else:
    sns = boto3.client('sns')
    
SNS_TOPIC_ARN = os.environ.get('SNS_TOPIC_ARN')

def handler(event, context):
    
    try:
        # Get user details from the authorizer
        claims = event.get('requestContext', {}).get('authorizer', {}).get('jwt', {}).get('claims', {})
        user_email = claims.get('email')
        user_id = claims.get('sub')

        if not user_id and IS_SAM_LOCAL:
            print("SAM LOCAL: Mocking user details.")
            user_email = "local-test@user.com"
            user_id = "local-test-user"
        elif not user_id and not IS_SAM_LOCAL:
            raise ValueError("Unauthorized: No user claims found in token.")

        # Get the website URL from the request body
        body = json.loads(event.get('body', '{}'))
        website_url = body.get('website_url', 'N/A')

        # Format the notification message
        subject = f"Manual Sentiment Check Requested: {website_url}"
        message = (
            f"A user has requested an immediate sentiment check.\n\n"
            f"User Email: {user_email}\n"
            f"User ID: {user_id}\n"
            f"Website: {website_url}\n\n"
            f"You can run the UptimeCheckerFunction manually in the AWS Lambda console to fulfill this request."
        )

        # Publish to the SNS topic
        # --- NEW: Mock SNS publish for local ---
        if IS_SAM_LOCAL:
            print("--- SAM LOCAL: MOCK SNS PUBLISH ---")
            print(f"Subject: {subject}")
            print(f"Message: {message}")
            print("--- END MOCK SNS PUBLISH ---")
        else:
            if not sns: # Safety check
                raise ValueError("SNS client not initialized for production.")
            sns.publish(
                TopicArn=SNS_TOPIC_ARN,
                Message=message,
                Subject=subject
            )

        return {
            'statusCode': 200,
            'headers': { 'Access-Control-Allow-Origin': '*' },
            'body': json.dumps({'message': 'Request sent successfully. The admin has been notified.'})
        }

    except Exception as e:
        print(f"Error: {e}")
        return {
            'statusCode': 500,
            'headers': { 'Access-Control-Allow-Origin': '*' },
            'body': json.dumps({'error': str(e)})
        }