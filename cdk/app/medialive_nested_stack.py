from aws_cdk import (
    CfnOutput,
    Fn,
    NestedStack,
    aws_medialive as medialive,
    aws_iam as iam
)

from aws_cdk.aws_ec2 import SecurityGroup, Peer, Port, SubnetType
from constructs import Construct
from app.network_nested_stack import NetworkNestedStack
from app.storage_nested_stack import StorageNestedStack
from cdk_nag import NagSuppressions


class MediaLiveNestedStack(NestedStack):

    def __init__(
            self,
            scope: Construct,
            construct_id: str,
            network: NetworkNestedStack,
            storage: StorageNestedStack,
            media_destinations: dict,
            stack_name: str,
            **kwargs) -> None:
            
        super().__init__(scope, construct_id, **kwargs)

        input_name = "protected_stream_input"
        channel_name = "protected_stream_channel"
        output_id = "protected-stream-output" # Destination IDs in MediaLive only allow letters, numbers and hyphens.
        s3destination = storage.media_bucket.bucket_name
        subnet_ids = [Fn.select(0, network.vpc.select_subnets().subnet_ids)] # We only select one subnet for the SINGLE_PIPELINE channel

        ### MediaLive IAM role definition
        medialive_role_name = f"{stack_name}_MediaLiveAccessRole"
        medialive_role = iam.CfnRole(
            self,
            medialive_role_name,
            description="MediaLive access role",
            role_name=medialive_role_name,
            assume_role_policy_document=iam.PolicyDocument(
                statements=[
                    iam.PolicyStatement(
                        actions=["sts:AssumeRole"],
                        principals=[
                            iam.ServicePrincipal("medialive.amazonaws.com")
                        ],
                        effect=iam.Effect.ALLOW
                    )
                ],
            ),
            policies=[
                iam.CfnRole.PolicyProperty(
                    policy_name="MediaLiveAccessPolicy",
                    policy_document=iam.PolicyDocument(
                        statements=[
                            iam.PolicyStatement(
                                effect=iam.Effect.ALLOW,
                                resources=['*'],
                                actions=[
                                    "ssm:Describe*",
                                    "ssm:Get*",
                                    "ssm:List*",
                                ]
                            ),
                            iam.PolicyStatement(
                                effect=iam.Effect.ALLOW,
                                resources=["*"],
                                actions=[
                                    "ec2:describeSubnets",
                                    "ec2:describeNetworkInterfaces",
                                    "ec2:createNetworkInterface",
                                    "ec2:createNetworkInterfacePermission",
                                    "ec2:deleteNetworkInterface",
                                    "ec2:deleteNetworkInterfacePermission",
                                    "ec2:describeSecurityGroups",
                                ]
                            ),
                            iam.PolicyStatement(
                                effect=iam.Effect.ALLOW,
                                resources=[storage.media_bucket.bucket_arn,  storage.media_bucket.bucket_arn + '/*'],
                                actions=[
                                    "s3:ListBucket",
                                    "s3:PutObject",
                                    "s3:GetObject",
                                    "s3:DeleteObject",
                                ]
                            ),
                            iam.PolicyStatement(
                                effect=iam.Effect.ALLOW,
                                resources=['*'],
                                actions=[
                                    "logs:CreateLogGroup",
                                    "logs:CreateLogStream",
                                    "logs:PutLogEvents",
                                    "logs:DescribeLogStreams",
                                    "logs:DescribeLogGroups",
                                ]
                            ),
                        ]
                    ),
                )
            ]
        )
        NagSuppressions.add_resource_suppressions(medialive_role, [
            {
                "id":"AwsSolutions-IAM5",
                "reason":"wildcard is only for resources being access by mediachannel which needs to create EC2 and associated log groups"
            }
        ])

        # MediaLive input security group
        input_secgrp = SecurityGroup(
            self,
            "MediaLiveInputSecGrp",
            vpc=network.vpc,
            allow_all_outbound=True,
            security_group_name="medialive_input_secgrp"
        )
        input_secgrp.add_ingress_rule(peer=Peer.ipv4(network.vpc.vpc_cidr_block),connection=Port.all_tcp())
        input_secgrp.add_ingress_rule(peer=Peer.ipv4(network.vpc.vpc_cidr_block),connection=Port.all_udp())

        ### Medialive input definition
        self.media_input = medialive.CfnInput(
            self,
            input_name,
            name=input_name,
            type="RTMP_PUSH",
            role_arn= medialive_role.attr_arn,
            vpc=medialive.CfnInput.InputVpcRequestProperty(
                security_group_ids=[input_secgrp.security_group_id], # VPC Inputs cannot use MediaLive Input Security Groups and use a VPC security group instead
                subnet_ids=subnet_ids
            ),
            destinations=[
                medialive.CfnInput.InputDestinationRequestProperty(stream_name="protected_stream_app/protected_stream_appinst1"),
            ]
        )


        ### MediaLive channel definition
        self.my_medialive_tx_channel = medialive.CfnChannel(
            self,
            channel_name,
            channel_class="SINGLE_PIPELINE",
            log_level="DEBUG",
            name=channel_name,
            role_arn=medialive_role.attr_arn,
            destinations=[
                medialive.CfnChannel.OutputDestinationProperty(
                    id=output_id,
                    settings=[
                        medialive.CfnChannel.OutputDestinationSettingsProperty(
                            url=f"{'s3ssl://'}{s3destination}{media_destinations['primary']}"
                        )
                    ]
                )
            ],
            input_specification=medialive.CfnChannel.InputSpecificationProperty(
                codec="AVC",
                maximum_bitrate="MAX_10_MBPS",
                resolution="HD"
            ),
            # Specifies the VPC subnets to output to
            vpc=medialive.CfnChannel.VpcOutputSettingsProperty(
                 subnet_ids = subnet_ids
            ),
            input_attachments=[medialive.CfnChannel.InputAttachmentProperty(
                input_id=self.media_input.ref,
                input_attachment_name=self.media_input.name,
                input_settings=medialive.CfnChannel.InputSettingsProperty(
                    audio_selectors=[],
                    caption_selectors=[],
                    input_filter="AUTO",
                    filter_strength=1,
                    deblock_filter="DISABLED",
                    denoise_filter="DISABLED",
                    smpte2038_data_preference="IGNORE",
                )
            )
            ],
            encoder_settings=medialive.CfnChannel.EncoderSettingsProperty(
                audio_descriptions=[
                    medialive.CfnChannel.AudioDescriptionProperty(
                        name="audio_desc_private",
                        audio_type_control="FOLLOW_INPUT",
                        language_code_control="FOLLOW_INPUT",
                    )
                ],
                output_groups=[
                    medialive.CfnChannel.OutputGroupProperty(
                        name="HLS_stream",
                        output_group_settings=medialive.CfnChannel.OutputGroupSettingsProperty(
                            hls_group_settings=medialive.CfnChannel.HlsGroupSettingsProperty(
                                destination=medialive.CfnChannel.OutputLocationRefProperty(
                                    destination_ref_id="protected-stream-output" # Generates "Status: 422; UnprocessableEntityException" if missing
                                ),
                                incomplete_segment_behavior="AUTO",
                                discontinuity_tags="INSERT",
                                segmentation_mode="USE_SEGMENT_DURATION",
                                hls_cdn_settings=medialive.CfnChannel.HlsCdnSettingsProperty(
                                    hls_s3_settings=medialive.CfnChannel.HlsS3SettingsProperty()
                                ),
                                input_loss_action="EMIT_OUTPUT",
                                manifest_compression="NONE",
                                iv_in_manifest="INCLUDE",
                                iv_source="FOLLOWS_SEGMENT_NUMBER",
                                client_cache="ENABLED",
                                ts_file_mode="SEGMENTED_FILES",
                                manifest_duration_format="FLOATING_POINT",
                                redundant_manifest="DISABLED",
                                output_selection="MANIFESTS_AND_SEGMENTS",
                                stream_inf_resolution="INCLUDE",
                                i_frame_only_playlists="DISABLED",
                                index_n_segments=20,
                                program_date_time="EXCLUDE",
                                program_date_time_period=600,
                                keep_segments=41,
                                segment_length=7,
                                timed_metadata_id3_frame="PRIV",
                                timed_metadata_id3_period=10,
                                hls_id3_segment_tagging="DISABLED",
                                codec_specification="RFC_4281",
                                directory_structure="SINGLE_DIRECTORY",
                                segments_per_subdirectory=10000,
                                mode="LIVE",
                                program_date_time_clock="INITIALIZE_FROM_OUTPUT_TIMECODE"
                            ),
                        ),
                        outputs=[
                            medialive.CfnChannel.OutputProperty(
                                output_settings=medialive.CfnChannel.OutputSettingsProperty(
                                    hls_output_settings=medialive.CfnChannel.HlsOutputSettingsProperty(
                                        hls_settings=medialive.CfnChannel.HlsSettingsProperty(
                                            standard_hls_settings=medialive.CfnChannel.StandardHlsSettingsProperty(
                                                m3_u8_settings=medialive.CfnChannel.M3u8SettingsProperty(
                                                    audio_frames_per_pes=4,
                                                    audio_pids="492-498",
                                                    ecm_pid="8182",
                                                    pcr_control="PCR_EVERY_PES_PACKET",
                                                    pmt_pid="480",
                                                    program_num=1,
                                                    scte35_pid="500",
                                                    scte35_behavior="NO_PASSTHROUGH",
                                                    timed_metadata_pid="502",
                                                    timed_metadata_behavior="NO_PASSTHROUGH",
                                                    video_pid="481"
                                                ),
                                                audio_rendition_sets="program_audio"
                                            )
                                        )
                                    ),
                                ),
                                output_name="video_720p",
                                video_description_name="video_desc_private",
                                audio_description_names=["audio_desc_private"],
                            ),
                        ]
                    )
                ],
                timecode_config=medialive.CfnChannel.TimecodeConfigProperty(
                    source="SYSTEMCLOCK",
                ),
                video_descriptions=[
                    medialive.CfnChannel.VideoDescriptionProperty(
                        name="video_desc_private",
                        height=720,
                        width=1280,
                        respond_to_afd="NONE",
                        sharpness=50,
                        scaling_behavior="DEFAULT",
                        codec_settings=medialive.CfnChannel.VideoCodecSettingsProperty(
                            h264_settings=medialive.CfnChannel.H264SettingsProperty(
                                afd_signaling="NONE",
                                color_metadata="INSERT",
                                adaptive_quantization="AUTO",
                                entropy_encoding="CABAC",
                                flicker_aq="ENABLED",
                                force_field_pictures="DISABLED",
                                framerate_control="INITIALIZE_FROM_SOURCE",
                                gop_b_reference="DISABLED",
                                gop_closed_cadence=1,
                                gop_num_b_frames=1,
                                gop_size=90,
                                gop_size_units="FRAMES",
                                subgop_length="FIXED",
                                scan_type="PROGRESSIVE",
                                level="H264_LEVEL_AUTO",
                                look_ahead_rate_control="MEDIUM",
                                num_ref_frames=1,
                                par_control="INITIALIZE_FROM_SOURCE",
                                profile="MAIN",
                                rate_control_mode="CBR",
                                syntax="DEFAULT",
                                scene_change_detect="ENABLED",
                                spatial_aq="ENABLED",
                                temporal_aq="ENABLED",
                                timecode_insertion="DISABLED"
                            )
                        )
                    ),
                ]
            ),
            tags={"StackName": stack_name}
        )

        # Outputs
        CfnOutput(self, "MediaLivePrimaryInput", value=Fn.select(0, self.media_input.attr_destinations))