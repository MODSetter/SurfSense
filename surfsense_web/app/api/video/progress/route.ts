import { NextRequest, NextResponse } from "next/server";
import {
	getRenderProgress,
	speculateFunctionName,
	type AwsRegion,
} from "@remotion/lambda/client";

const REGION = process.env.REMOTION_AWS_REGION || "us-east-1";
const RAM = Number(process.env.REMOTION_LAMBDA_RAM || 3009);
const DISK = Number(process.env.REMOTION_LAMBDA_DISK || 10240);
const TIMEOUT = Number(process.env.REMOTION_LAMBDA_TIMEOUT || 240);

export async function POST(req: NextRequest) {
	try {
		const body = await req.json();
		const { id, bucketName } = body;

		if (!id || !bucketName) {
			return NextResponse.json(
				{ type: "error", message: "id and bucketName are required" },
				{ status: 400 },
			);
		}

		const renderProgress = await getRenderProgress({
			bucketName,
			functionName: speculateFunctionName({
				diskSizeInMb: DISK,
				memorySizeInMb: RAM,
				timeoutInSeconds: TIMEOUT,
			}),
			region: REGION as AwsRegion,
			renderId: id,
		});

		if (renderProgress.fatalErrorEncountered) {
			return NextResponse.json({
				type: "success",
				data: { type: "error", message: renderProgress.errors[0].message },
			});
		}

		if (renderProgress.done) {
			return NextResponse.json({
				type: "success",
				data: {
					type: "done",
					url: renderProgress.outputFile as string,
					size: renderProgress.outputSizeInBytes as number,
				},
			});
		}

		return NextResponse.json({
			type: "success",
			data: {
				type: "progress",
				progress: Math.max(0.03, renderProgress.overallProgress),
			},
		});
	} catch (err) {
		return NextResponse.json(
			{ type: "error", message: (err as Error).message },
			{ status: 500 },
		);
	}
}
