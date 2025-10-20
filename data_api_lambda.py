import json
import boto3
import os

dynamodb = boto3.resource('dynamodb')
table_name = os.environ.get('DYNAMODB_TABLE')
table = dynamodb.Table(table_name)

def handler(event, context):
    http_method = event['httpMethod']
    
    if http_method == 'GET':
        response = table.scan()
        return {
            'statusCode': 200,
            'headers': {
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps(response.get('Items', []))
        }
        
    elif http_method == 'POST':
        try:
            body = json.loads(event['body'])
            website_url = body.get('website_url')
            twitter_keyword = body.get('twitter_keyword')

            if not website_url or not twitter_keyword:
                return {'statusCode': 400, 'body': json.dumps({'error': 'website_url and twitter_keyword are required'})}

            table.put_item(
                Item={
                    'website_url': website_url,
                    'twitter_keyword': twitter_keyword,
                    'status': 'PENDING',
                    'sentiment_score': '0.0'
                }
            )
            return {
                'statusCode': 201,
                'headers': {
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({'message': 'Website added successfully'})
            }
        except Exception as e:
            return {'statusCode': 500, 'body': json.dumps({'error': str(e)})}
            
    return {
        'statusCode': 405,
        'body': json.dumps({'error': 'Method Not Allowed'})
    }
