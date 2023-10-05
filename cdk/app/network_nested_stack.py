from typing import Sequence
from aws_cdk import (
    NestedStack,
    aws_ec2 as ec2
)
from constructs import Construct
from cdk_nag import NagSuppressions

class NetworkNestedStack(NestedStack):
    
    def __init__(self, 
            scope: Construct, 
            construct_id: str, 
            stack_name = str,
            client_vpn_cert = str,
            server_vpn_cert = str,
            **kwargs) -> None:

        super().__init__(scope, construct_id, **kwargs)
        
        
        # Set up VPC with private subnets
        self.vpc = ec2.Vpc(
            self, 
            "ProtectedMediaStreamingVpc",
            ip_addresses=ec2.IpAddresses.cidr("10.0.0.0/16"),  # Change to your preferred VPC CIDR range
            max_azs=2,                          # default is all AZs in region
            nat_gateways=0,                     # Number of NAT Gateways needed
            vpc_name="ProtectedMediaStreaming",       # Associated with tag Name
            subnet_configuration=[
                ec2.SubnetConfiguration(
                    name="ProtectedMediaStreaming",
                    subnet_type=ec2.SubnetType.PRIVATE_ISOLATED,
                    cidr_mask=20
            )],
            enable_dns_hostnames=True,
            enable_dns_support=True
            
        )
        self.vpc.add_client_vpn_endpoint(
            id="media-vpn-endpoint",
            cidr="10.0.128.0/20",  # Change this if you change the VPC CIDR range above
            authorize_all_users_to_vpc_cidr=True,
            vpc_subnets=ec2.SubnetSelection(one_per_az=True),
            server_certificate_arn=server_vpn_cert,
            client_certificate_arn=client_vpn_cert,
        )

        self.s3_vpc_gateway_endpoint = self.vpc.add_gateway_endpoint("MediaBucketEndpoint", service=ec2.GatewayVpcEndpointAwsService.S3) # Endpoint is routable from all subnets in VPC by default