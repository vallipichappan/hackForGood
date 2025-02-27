from aws_cdk import (
    Stack,
    aws_lambda as _lambda,
    aws_apigateway as apigw,
    aws_secretsmanager as secretsmanager,
    aws_opensearchservice as opensearch,
    aws_iam as iam,
    Duration,
    CfnOutput,
    SecretValue,
)
from constructs import Construct
import json
import subprocess
from aws_cdk import Duration

class WhatsAppAIStack(Stack):
    def __init__(self, scope: Construct, id: str, **kwargs) -> None:
        super().__init__(scope, id, **kwargs)
        
        # Create Secret for WhatsApp credentials
        whatsapp_secret = secretsmanager.Secret(
            self, 'WhatsAppSecret',
            secret_string_value=SecretValue.unsafe_plain_text(json.dumps({
                'whatsapp_token': '',
                'phone_number_id': '',
                'verify_token': ''
            }))
        )

        # dependencies_layer = _lambda.LayerVersion(
        #     self, 'DependenciesLayer',
        #     code=_lambda.Code.from_asset('lambda_layer.zip'),
        #     compatible_runtimes=[_lambda.Runtime.PYTHON_3_11],
        #     description='Layer containing dependencies for WhatsApp AI Lambda'
        # )

        # Lambda function
        whatsapp_handler = _lambda.Function(
            self, 'WhatsAppHandler',
            runtime=_lambda.Runtime.PYTHON_3_11,
            code=_lambda.Code.from_asset('lambda_package.zip'),
            handler='whatsapp_handler.handle',
            # layers=[dependencies_layer],
            timeout=Duration.seconds(60),
            environment={
                'WHATSAPP_TOKEN': whatsapp_secret.secret_value_from_json('whatsapp_token').unsafe_unwrap(),
                'PHONE_NUMBER_ID': whatsapp_secret.secret_value_from_json('phone_number_id').unsafe_unwrap(),
                'VERIFY_TOKEN': whatsapp_secret.secret_value_from_json('verify_token').unsafe_unwrap(),
            }
        )

        # whatsapp_handler = _lambda.DockerImageFunction(
        #     self, 'WhatsAppHandler',
        #     code=_lambda.DockerImageCode.from_image_asset('docker-lambda'),
        #     timeout=Duration.seconds(60),
        #     environment={
        #         'WHATSAPP_TOKEN': whatsapp_secret.secret_value_from_json('whatsapp_token').unsafe_unwrap(),
        #         'PHONE_NUMBER_ID': whatsapp_secret.secret_value_from_json('phone_number_id').unsafe_unwrap(),
        #         'VERIFY_TOKEN': whatsapp_secret.secret_value_from_json('verify_token').unsafe_unwrap(),
        #     }
        # )

        whatsapp_handler.add_to_role_policy(iam.PolicyStatement(
            actions=[
                "bedrock:ListFoundationModels",
                "bedrock:GetFoundationModel",
                "bedrock-runtime:InvokeModel"
            ],
            resources=["*"]
        ))


        # API Gateway
        api = apigw.RestApi(
            self, 'WhatsAppAPI',
            rest_api_name='WhatsApp AI API',
            default_cors_preflight_options=apigw.CorsOptions(
                allow_origins=apigw.Cors.ALL_ORIGINS,
                allow_methods=apigw.Cors.ALL_METHODS
            )
        )

        webhook = api.root.add_resource('webhook')
        webhook.add_method('POST', apigw.LambdaIntegration(whatsapp_handler))
        webhook.add_method('GET', apigw.LambdaIntegration(whatsapp_handler))  

        CfnOutput(self, "WhatsAppEndpointA4043092", value=f"{api.url}webhook")
