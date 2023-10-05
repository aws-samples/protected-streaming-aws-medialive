#!/usr/bin/env python3
import os, sys
import aws_cdk as cdk
from app.iam_nested_stack import IamNestedStack
from app.api_nested_stack import ApiNestedStack
from app.network_nested_stack import NetworkNestedStack
from app.medialive_nested_stack import MediaLiveNestedStack
from app.storage_nested_stack import StorageNestedStack
from app.protected_streaming_root_stack import ProtectedStreamingRoot
from cdk_nag import AwsSolutionsChecks
from aws_cdk import Aspects
from cdk_nag import NagSuppressions

### UPDATE THESE TWO VARIABLES WITH ARNs OF YOUR VPN CLIENT AND SERVER CERTIFICATES
my_client_vpn_cert_param = ""
my_server_vpn_cert_param = ""
if (my_client_vpn_cert_param == "" or my_server_vpn_cert_param == ""):
    print("Update the client and server certificate ARNs in the app.py file")
    sys.exit(1) # Exit with error

app = cdk.App()
env = cdk.Environment(account=os.environ['CDK_DEFAULT_ACCOUNT'], region=os.environ['CDK_DEFAULT_REGION'])

my_stack_name = "protected_streaming"


my_media_destinations = {
    "primary": "/pipe-1/media",
    "secondary": "/pipe-2/media"
}

root_stack = ProtectedStreamingRoot(app, "ProtectedStreaming", env=env)

network_stack = NetworkNestedStack(root_stack, "Network", 
    client_vpn_cert=my_client_vpn_cert_param, 
    server_vpn_cert=my_server_vpn_cert_param,
    stack_name=my_stack_name)
iam_stack = IamNestedStack(root_stack, "Security")
storage_stack = StorageNestedStack(root_stack, "Storage", 
    security=iam_stack,
    network=network_stack,
    stack_name=my_stack_name)
gateway_stack = ApiNestedStack(root_stack, "Gateway", 
    security=iam_stack,
    network=network_stack, 
    storage=storage_stack,
    media_destinations=my_media_destinations,
    stack_name=my_stack_name)
medialive_stack = MediaLiveNestedStack(root_stack, "MediaLive", 
    network=network_stack, 
    storage=storage_stack,
    media_destinations=my_media_destinations, 
    stack_name=my_stack_name)

Aspects.of(app).add(AwsSolutionsChecks(verbose=True))
# adding suppressions and justifications
NagSuppressions.add_stack_suppressions(iam_stack, [{"id":"AwsSolutions-IAM5", "reason":"resources are added to the policy in the storage stack, done to avoid circular dependencies"}])
NagSuppressions.add_stack_suppressions(network_stack,[{"id":"AwsSolutions-VPC7", "reason":"flow logs are not created to reduce cost impact on customer"}])
NagSuppressions.add_stack_suppressions(gateway_stack,[
    {"id":"AwsSolutions-COG4", "reason":"the API gateway created is private, can only be accessed when customer has set up their VPN to connect to the private VPC endpoint. Solution does not require cognito for authentication"},
    {"id":"AwsSolutions-APIG6", "reason":"the API gateway created is private, can only be accessed when customer has set up their VPN to connect to the private VPC endpoint. Solution does not require cognito for authentication"},
    {"id":"AwsSolutions-APIG4", "reason":"the API gateway created is private, can only be accessed when customer has set up their VPN to connect to the private VPC endpoint. Solution does not require cognito for authentication"},
    {"id":"AwsSolutions-APIG1", "reason":"the API gateway created is private, can only be accessed when customer has set up their VPN to connect to the private VPC endpoint. Solution does not require cognito for authentication"},
    {"id":"AwsSolutions-APIG2", "reason":"the API gateway created is private, can only be accessed when customer has set up their VPN to connect to the private VPC endpoint. Solution does not require cognito for authentication"}
    ])
NagSuppressions.add_stack_suppressions(storage_stack,[
    {"id":"AwsSolutions-S1", "reason":"customer can choose to enable server access logging as part of their logging strategy as they deploy this solution"}
    
    ])
app.synth()