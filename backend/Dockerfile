FROM public.ecr.aws/lambda/python:3.13

COPY requirements-lambda.txt /tmp/requirements-lambda.txt
RUN python -m pip install --no-cache-dir \
    --requirement /tmp/requirements-lambda.txt --target "${LAMBDA_TASK_ROOT}"

COPY src/alphaforge/ ${LAMBDA_TASK_ROOT}/alphaforge/

CMD ["alphaforge.presentation.lambda_handler.handler"]
