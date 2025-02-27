import aws_cdk as core
import aws_cdk.assertions as assertions

from whatsapp_ai_bot.whatsapp_ai_stack import WhatsappAiBotStack

# example tests. To run these tests, uncomment this file along with the example
# resource in whatsapp_ai_bot/whatsapp_ai_bot_stack.py
def test_sqs_queue_created():
    app = core.App()
    stack = WhatsappAiBotStack(app, "whatsapp-ai-bot")
    template = assertions.Template.from_stack(stack)

#     template.has_resource_properties("AWS::SQS::Queue", {
#         "VisibilityTimeout": 300
#     })
