##########################
# Bootstrapping variables
##########################

AWS_BRANCH?="dev"
STACK_NAME?="mlopsintro"
#DEPLOYMENT_BUCKET_NAME?="UNDEFINED"
DEPLOYMENT_BUCKET_PREFIX?=""
SAM_BUILD_EXTRA_ARGS?=""

target:
	$(info ${HELP_MESSAGE})
	@exit 0

init: ##=> Install OS deps and dev tools
	$(info [*] Bootstrapping CI system...)
	@$(MAKE) _install_os_packages

build: ##=> Build SAM template & assets to CloudFormation on S3
	$(info [*] Building AWS SAM stack...)
	sam build \
			--use-container \
			--template project.sam.yaml \
			$(SAM_BUILD_EXTRA_ARGS) && \
		sam package \
			--s3-bucket $${DEPLOYMENT_BUCKET_NAME} \
			--s3-prefix $${DEPLOYMENT_BUCKET_PREFIX}sam \
			--output-template-file project.tmp.yaml && \
		aws s3 cp project.tmp.yaml \
			s3://$${DEPLOYMENT_BUCKET_NAME}/$${DEPLOYMENT_BUCKET_PREFIX}project.cf.yaml
	sam build \
			--use-container \
			--template environment.sam.yaml \
			$(SAM_BUILD_EXTRA_ARGS) && \
		sam package \
			--s3-bucket $${DEPLOYMENT_BUCKET_NAME} \
			--s3-prefix $${DEPLOYMENT_BUCKET_PREFIX}sam \
			--output-template-file environment-presub.tmp.yaml && \
		export MLProjectCFURL=https://$${DEPLOYMENT_BUCKET_NAME}.s3.`aws configure get region`.amazonaws.com/$${DEPLOYMENT_BUCKET_PREFIX}project.cf.yaml && \
		envsubst '$$MLProjectCFURL' <environment-presub.tmp.yaml >environment.tmp.yaml && \
		aws s3 cp environment.tmp.yaml \
			s3://$${DEPLOYMENT_BUCKET_NAME}/$${DEPLOYMENT_BUCKET_PREFIX}environment.cf.yaml
	# (We use envsubst to replace the Project CF template URL in the environment template with the built &
	# staged version)

create: ##=> Create environment stack (only)
	$(info [*] Deploying...)
	# This option disables rollback for debugging, versus SAM `deploy`
	aws cloudformation create-stack \
			--template-body file://environment.tmp.yaml \
			--stack-name $(STACK_NAME) \
			--capabilities CAPABILITY_IAM CAPABILITY_AUTO_EXPAND \
			--disable-rollback
			# (disable rollback for debugging)
			# TODO: Support --parameters through MAKE?

create.project: ##=> Create project stack (only)
	$(info [*] Deploying...)
	# This option disables rollback for debugging, versus SAM `deploy`
	aws cloudformation create-stack \
			--template-body file://project.tmp.yaml \
			--stack-name $(STACK_NAME) \
			--capabilities CAPABILITY_IAM CAPABILITY_AUTO_EXPAND \
			--disable-rollback
			# --parameters ParameterKey=StudioUsers,ParameterValue=tmpuser
			# TODO: Support --parameters through MAKE?

deploy: ##=> Deploy environment (flexible create or update)
	$(info [*] Deploying...)
	sam deploy \
			--template-file environment.tmp.yaml \
			--stack-name $(STACK_NAME) \
			--capabilities CAPABILITY_IAM
			# TODO: Support --parameter-overrides through MAKE?

deploy.project: ##=> Deploy project stack (flexible create or update)
	$(info [*] Deploying...)
	sam deploy \
			--template-file project.tmp.yaml \
			--stack-name $(STACK_NAME) \
			--capabilities CAPABILITY_IAM
			# TODO: Support --parameter-overrides through MAKE?

all: ##=> Build and create stack
	@$(MAKE) build
	@$(MAKE) create

delete: ##=> Delete services
	$(info [*] Deleting stack...)
	aws cloudformation delete-stack --stack-name $(STACK_NAME)


#############
#  Helpers  #
#############

_install_os_packages:
	$(info [*] Installing jq...)
	yum install jq -y
	$(info [*] Checking currently installed Python version...)
	python3 --version
	$(info [*] Upgrading Python SAM CLI and CloudFormation linter to the latest version...)
	python3 -m pip install --upgrade --user cfn-lint aws-sam-cli
	npm -g install aws-cdk

define HELP_MESSAGE

	Environment variables:

	AWS_BRANCH: "dev"
		Description: Probably not needed...
	DEPLOYMENT_BUCKET_NAME: "my-bucket"
		Description: Amazon S3 bucket for staging built SAM Lambda bundles and assets
	DEPLOYMENT_BUCKET_PREFIX: "a/prefix/"
		Description: For publishing to a prefix in your deployment bucket, instead of root
	STACK_NAME: "sm101stack"
		Description: Stack Name to deploy/redeploy to
	SAM_BUILD_EXTRA_ARGS: ""
		Description: Extra arguments to pass to AWS SAM build, if necessary

	Common usage:

	...::: Bootstraps environment with necessary tools like SAM CLI, cfn-lint, etc. :::...
	$ make init

	...::: Build all SAM based services :::...
	$ make build

	...::: Deploy or re-deploy all SAM based services :::...
	$ make deploy

	...::: Delete all SAM based services :::...
	$ make delete
endef
