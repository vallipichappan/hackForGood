FROM public.ecr.aws/lambda/python:3.11

# Copy requirements.txt
COPY lambda_module/requirements.txt ${LAMBDA_TASK_ROOT}

# Install the dependencies
RUN pip install -r requirements.txt

# Copy function code
COPY lambda_module/whatsapp_handler.py ${LAMBDA_TASK_ROOT}
COPY lambda_module/multiagent_handler.py ${LAMBDA_TASK_ROOT}

# Set the CMD to your handler
CMD [ "whatsapp_handler.handle" ]