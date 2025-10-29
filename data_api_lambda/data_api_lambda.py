import json
import boto3
import boto3.dynamodb.conditions
import os 

# Check if running in a local SAM environment
IS_SAM_LOCAL = os.environ.get('AWS_SAM_LOCAL')
if IS_SAM_LOCAL:
    # If so, connect to the local DynamoDB instance
    dynamodb = boto3.resource('dynamodb', endpoint_url='http://host.docker.internal:8000')
else:
    # Otherwise, connect to the DynamoDB in the cloud
    dynamodb = boto3.resource('dynamodb')

TABLE_NAME = os.environ.get('DYNAMODB_TABLE')
if not TABLE_NAME:
    raise ValueError("FATAL ERROR: DYNAMODB_TABLE environment variable not set.")
table = dynamodb.Table(TABLE_NAME)

def handler(event, context):
    """
    Handles API Gateway requests for managing websites.
    """
    print(f"Received event: {json.dumps(event)}")
    
    # FIX: Use .get() to safely find the http_method from the new event structure
    http_method = event.get('httpMethod') or event.get('requestContext', {}).get('httpMethod')
    
    # Local SAM Testing get() to delete websites function
    # This nested .get() chain prevents a KeyError if any key is missing
    user_id_claims = event.get('requestContext', {}).get('authorizer', {}).get('jwt', {}).get('claims', {})
    user_id = user_id_claims.get('sub')
    
    if not user_id and IS_SAM_LOCAL:
        print("SAM LOCAL: Mocking user_id for local testing.")
        user_id = "local-test-user" # Provide a mock ID for local tests
    
    if not user_id and not IS_SAM_LOCAL:
        print("Production Error: No user_id found in token.")
        return {'statusCode': 401, 'body': json.dumps({'error': 'Unauthorized: Missing or invalid token claims'})}

    try:
        if http_method == 'GET':
            # --- GET /websites ---
            print(f"Processing GET for user: {user_id}")
            # FIX: Filter websites by user_id
            response = table.scan(
                FilterExpression=boto3.dynamodb.conditions.Attr('user_id').eq(user_id)
            )
            items = response.get('Items', [])
            
            return {
                'statusCode': 200,
                'headers': { 'Access-Control-Allow-Origin': '*' },
                'body': json.dumps(items)
            }

        elif http_method == 'POST':
            # --- POST /websites ---
            body = json.loads(event.get('body', '{}'))
            print(f"Processing POST for user: {user_id}")
            
            item = {
                'website_url': body['website_url'],
                'twitter_keyword': body['twitter_keyword'],
                'user_id': user_id, # FIX: Add the user_id to the item
                'status': 'Pending',
                'sentiment_score': '0.0',
                'example_tweets': []
            }
            
            table.put_item(Item=item)
            
            return {
                'statusCode': 201,
                'headers': { 'Access-Control-Allow-Origin': '*' },
                'body': json.dumps({'message': 'Website added successfully'})
            }

        elif http_method == 'DELETE':
            # --- UPDATED: DELETE /websites ---
            body = json.loads(event.get('body', '{}'))
            print(f"Processing DELETE for user: {user_id}")
            website_url_to_delete = body.get('website_url')

            if not website_url_to_delete:
                raise ValueError("website_url not provided for deletion")

            if IS_SAM_LOCAL:
                # FIX: For local testing, we can't verify the user_id, so we do a simple delete.
                print("SAM LOCAL: Skipping user_id check for DELETE")
                table.delete_item(
                    Key={'website_url': website_url_to_delete}
                )
            else:
                # In production, enforce the security check.
                print("Production: Enforcing user_id check for DELETE")
                table.delete_item(
                    Key={'website_url': website_url_to_delete},
                    ConditionExpression="user_id = :uid",
                    ExpressionAttributeValues={":uid": user_id}
                )
            
            return {
                'statusCode': 200,
                'headers': { 'Access-Control-Allow-Origin': '*' },
                'body': json.dumps({'message': 'Website deleted successfully'})
            }

    except Exception as e:
        print(f"Error: {e}")
        return {
            'statusCode': 500,
            'headers': { 'Access-Control-Allow-Origin': '*' },
            'body': json.dumps({'error': str(e)})
        }
    
    # Fallback for unhandled methods
    return {
        'statusCode': 400,
        'headers': { 'Access-Control-Allow-Origin': '*' },
        'body': json.dumps({'error': 'Unsupported HTTP method'})
    }
