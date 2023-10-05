from aws_cdk import (
    NestedStack,
    CfnOutput,
    aws_apigateway as apigateway,
    aws_ec2 as ec2,
    aws_iam as iam
)
from constructs import Construct
from app.network_nested_stack import NetworkNestedStack
from app.storage_nested_stack import StorageNestedStack
from app.iam_nested_stack import IamNestedStack

class ApiNestedStack(NestedStack):

    def __init__(self, 
            scope: Construct, 
            construct_id: str, 
            security: IamNestedStack,
            network: NetworkNestedStack, 
            storage: StorageNestedStack, 
            media_destinations: dict,
            stack_name = str,
            **kwargs) -> None:

        super().__init__(scope, construct_id, **kwargs)


        vpc = network.vpc
        bucket = storage.media_bucket

        ### S3 AWS service integration ###
        
        apigw_s3_integration_options = apigateway.IntegrationOptions(
            credentials_role=security.apigw_svc_role,
            integration_responses=[
                apigateway.IntegrationResponse(
                    status_code="200",
                    response_parameters={"method.response.header.Content-Type": "integration.response.header.Content-Type"}
                )
            ],
            request_parameters={        # Map {proxy} from the method request path to the integration request path
                "integration.request.path.proxy": "method.request.path.proxy"
            }
        )

        apigw_s3_integration = apigateway.AwsIntegration(
            service="s3",
            integration_http_method="GET",
            path=bucket.bucket_name+"/{proxy}",  # The path needs to contain the bucket name and then the [proxy] path
            options=apigw_s3_integration_options
        )

        ### VPC Endpoint for API Gateway ###

        apigw_vpc_endpoint = vpc.add_interface_endpoint(
                                "ProtectedStreamingApiGatewayEndpoint", 
                                service=ec2.InterfaceVpcEndpointAwsService.APIGATEWAY,
                                private_dns_enabled=True,
                            ) # Endpoint is routable from all subnets in VPC by default
        
        # Policy allows access to execute API
        apigw_vpc_endpoint_policy = iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            principals=[iam.AnyPrincipal()],
            actions=["execute-api:Invoke"],
            resources=["*"]
        )
        # Bucket specific policy added to VPC gateway endpoint
        apigw_vpc_endpoint.add_to_policy(statement=apigw_vpc_endpoint_policy)

        ### API Gateway REST API ###

        # API resource policy
        apigw_api_resource_policy = iam.PolicyDocument(
            statements=[
                iam.PolicyStatement(
                    effect=iam.Effect.DENY,
                    principals=[iam.AnyPrincipal()],
                    actions=["execute-api:Invoke"],
                    resources=["*"],
                    conditions={"StringNotEquals": {
                                    "aws:sourceVpc": vpc.vpc_id
                                }
                    }
                ),
                iam.PolicyStatement(
                    effect=iam.Effect.ALLOW,
                    principals=[iam.AnyPrincipal()],
                    actions=["execute-api:Invoke"],
                    resources=["*"]
                )
            ]
        )

        # Create REST API
        api = apigateway.RestApi(self, "private-stream-api",
            rest_api_name="Protected Media Streaming",
            description="This API streams video from an S3 bucket.",
            binary_media_types=["*/*"],                     # Configure for binary media types to allow video to be served
            endpoint_configuration=apigateway.EndpointConfiguration(
                types=[apigateway.EndpointType.PRIVATE],    # Private endpoint in the VPC
                vpc_endpoints=[apigw_vpc_endpoint]          # Use the VPC interface endpoint set up above
            ),
            policy=apigw_api_resource_policy
        )

        # Add resources to the API 
        # The path for the API will be /{stage}/{resource}, for example /prod/index.html
        api.root.add_resource("{proxy+}").add_method(
            "GET",
            apigw_s3_integration,
            method_responses=[
                apigateway.MethodResponse(
                    status_code="200",
                    response_parameters={"method.response.header.Content-Type": True}
                )
            ],
            request_parameters={        # {prefix} and {key} are mapped from the request path
                "method.request.path.proxy": True,
                "method.request.header.Content-Type": True
            }
        )

        # Outputs
        CfnOutput(self, "VideoManifestPrimaryURL", value=f"{api.url.strip('/')}{media_destinations['primary']}{'/media_1.m3u8'}")
        
        