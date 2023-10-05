from aws_cdk import (
    NestedStack,
    RemovalPolicy,
    aws_s3 as s3,
    aws_ec2 as ec2,
    aws_iam as iam
)
from constructs import Construct
from app.network_nested_stack import NetworkNestedStack
from cdk_nag import NagSuppressions

class IamNestedStack(NestedStack):
    def __init__(self, 
            scope: Construct, 
            construct_id: str, 
            stack_name = str,
            **kwargs) -> None:
        
        super().__init__(scope, construct_id, **kwargs)

        # Policy restricts access to specific bucket through the VPC gateway endpoint
        self.vpc_s3_gw_endpoint_policy = iam.PolicyStatement(
            principals=[iam.AnyPrincipal()],
            effect=iam.Effect.ALLOW,
            actions=[
                "s3:Get*",
                "s3:Put*",
                "s3:List*",
                "s3:DeleteObject"
            ]
            # The resource section pointing to the bucket is added later when the bucket ARN is known
        )

        # API Gateway service policy
        self.apigw_svc_policy = iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=[
                "s3:Get*",
                "s3:List*"
            ]
            # The resource section pointing to the bucket is added later when the bucket ARN is known
        )        

        # API Gateway service role
        self.apigw_svc_role = iam.Role(self,"ApiGatewayRole",
            assumed_by=iam.ServicePrincipal("apigateway.amazonaws.com"),
            description="Used by API Gateway to access S3"
        )
