import { NextRequest, NextResponse } from "next/server";
import {
	renderMediaOnLambda,
	speculateFunctionName,
	type AwsRegion,
} from "@remotion/lambda/client";

const REGION = process.env.REMOTION_AWS_REGION || "us-east-1";
const SITE_NAME = process.env.REMOTION_SITE_NAME || "surfsense-video";
const RAM = Number(process.env.REMOTION_LAMBDA_RAM || 3009);
const DISK = Number(process.env.REMOTION_LAMBDA_DISK || 10240);
const TIMEOUT = Number(process.env.REMOTION_LAMBDA_TIMEOUT || 240);
const COMPOSITION_ID = "SurfSenseVideo";

export async function POST(req: NextRequest) {
	try {
		const body = await req.json();
		const { inputProps } = body;

		if (!inputProps?.scenes?.length) {
			return NextResponse.json(
				{ type: "error", message: "inputProps with scenes is required" },
				{ status: 400 },
			);
		}

		if (
			!process.env.AWS_ACCESS_KEY_ID &&
			!process.env.REMOTION_AWS_ACCESS_KEY_ID
		) {
			return NextResponse.json(
				{ type: "error", message: "AWS credentials not configured for video rendering" },
				{ status: 500 },
			);
		}

		const result = await renderMediaOnLambda({
			codec: "h264",
			functionName: speculateFunctionName({
				diskSizeInMb: DISK,
				memorySizeInMb: RAM,
				timeoutInSeconds: TIMEOUT,
			}),
			region: REGION as AwsRegion,
			serveUrl: SITE_NAME,
			composition: COMPOSITION_ID,
			inputProps,
			framesPerLambda: 10,
			downloadBehavior: {
				type: "download",
				fileName: "video.mp4",
			},
		});

		return NextResponse.json({ type: "success", data: result });
	} catch (err) {
		return NextResponse.json(
			{ type: "error", message: (err as Error).message },
			{ status: 500 },
		);
	}
}
