from aws_cdk import (
    CfnOutput,
    NestedStack,
    RemovalPolicy,
    aws_s3 as s3,
    aws_ec2 as ec2,
    aws_iam as iam
)
from constructs import Construct
from app.iam_nested_stack import IamNestedStack
from app.network_nested_stack import NetworkNestedStack

class StorageNestedStack(NestedStack):

    def __init__(self, 
            scope: Construct, 
            construct_id: str, 
            security: IamNestedStack,
            network: NetworkNestedStack, 
            stack_name = str,
            **kwargs) -> None:
        
        super().__init__(scope, construct_id, **kwargs)

        
        self.media_bucket = s3.Bucket(self, 
            "MediaBucket",
            removal_policy=RemovalPolicy.DESTROY,   # Remove if you wish for the media bucket to remain after you have destroyed the stack
            auto_delete_objects=True,                # Remove if you wish for the media bucket to remain after you have destroyed the stack
            enforce_ssl=True
        )
        self._bucket_name = self.media_bucket.bucket_name
        

        # Bucket specific resource restrictions added to VPC gateway endpoint policy
        security.vpc_s3_gw_endpoint_policy.add_resources(self.media_bucket.bucket_arn)
        security.vpc_s3_gw_endpoint_policy.add_resources(self.media_bucket.bucket_arn+"/*")
        network.s3_vpc_gateway_endpoint.add_to_policy(statement=security.vpc_s3_gw_endpoint_policy)

        # Bucket specific resource restrictions added to API Gateway service role
        security.apigw_svc_policy.add_resources(self.media_bucket.bucket_arn)
        security.apigw_svc_policy.add_resources(self.media_bucket.bucket_arn+"/*")
        security.apigw_svc_role.add_to_policy(security.apigw_svc_policy)

        # Outputs
        CfnOutput(self, "MediaBucketName", value=self._bucket_name)
    
    def get_bucket_name(self):
        return self._bucket_name
    
