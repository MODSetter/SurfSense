"use client";

import { Plus, Trash2 } from "lucide-react";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
	Select,
	SelectContent,
	SelectItem,
	SelectTrigger,
	SelectValue,
} from "@/components/ui/select";

interface InferenceParamsEditorProps {
	params: Record<string, number | string>;
	setParams: (newParams: Record<string, number | string>) => void;
}

const PARAM_KEYS = ["temperature", "max_tokens", "top_k", "top_p"] as const;

export default function InferenceParamsEditor({ params, setParams }: InferenceParamsEditorProps) {
	const [selectedKey, setSelectedKey] = useState<string>("");
	const [value, setValue] = useState<string>("");

	const handleAdd = () => {
		if (!selectedKey || value === "") return;

		if (params[selectedKey]) {
			alert(`${selectedKey} already exists`);
			return;
		}

		const numericValue = Number(value);

		if (
			(selectedKey === "temperature" || selectedKey === "top_p") &&
			(isNaN(numericValue) || numericValue < 0 || numericValue > 1)
		) {
			alert("Value must be a number between 0 and 1");
			return;
		}

		if (
			(selectedKey === "max_tokens" || selectedKey === "top_k") &&
			(!Number.isInteger(numericValue) || numericValue < 0)
		) {
			alert("Value must be a non-negative integer");
			return;
		}

		setParams({
			...params,
			[selectedKey]: isNaN(numericValue) ? value : numericValue,
		});

		setSelectedKey("");
		setValue("");
	};

	const handleDelete = (key: string) => {
		const newParams = { ...params };
		delete newParams[key];
		setParams(newParams);
	};

	return (
		<div className="space-y-6 p-2 sm:p-0">
			<div className="grid grid-cols-1 gap-4 md:grid-cols-[1fr_1fr_auto] md:gap-3 items-end">
				<div className="flex flex-col space-y-1">
					<Label htmlFor="param-key" className="text-sm font-medium">
						Parameter Key
					</Label>
					<Select value={selectedKey} onValueChange={setSelectedKey}>
						<SelectTrigger id="param-key" className="w-full">
							<SelectValue placeholder="Select parameter" />
						</SelectTrigger>
						<SelectContent>
							{PARAM_KEYS.map((key) => (
								<SelectItem key={key} value={key}>
									{key}
								</SelectItem>
							))}
						</SelectContent>
					</Select>
				</div>

				<div className="flex flex-col space-y-1">
					<Label htmlFor="param-value" className="text-sm font-medium">
						Value
					</Label>
					<Input
						id="param-value"
						placeholder="Enter value (e.g., 0.7 or 512)"
						value={value}
						onChange={(e) => setValue(e.target.value)}
						className="w-full"
					/>
				</div>

				<Button
					className="w-full md:w-auto h-10 mt-0"
					onClick={handleAdd}
					disabled={!selectedKey || value === ""}
				>
					<Plus className="w-4 h-4 mr-2" /> Add Parameter
				</Button>
			</div>

			<hr className="my-4" />

			{Object.keys(params).length > 0 && (
				<div className="border rounded-lg shadow-sm overflow-x-auto">
					<table className="min-w-full text-left text-sm divide-y divide-gray-200">
						<thead className="bg-black dark:bg-black">
							<tr>
								<th className="px-4 py-3 text-xs font-semibold uppercase tracking-wider text-gray-600 dark:text-gray-300">
									Key
								</th>
								<th className="px-4 py-3 text-xs font-semibold uppercase tracking-wider text-gray-600 dark:text-gray-300">
									Value
								</th>
								<th className="px-4 py-3 text-xs font-semibold uppercase tracking-wider text-gray-600 dark:text-gray-300 sr-only md:not-sr-only">
									Actions
								</th>
							</tr>
						</thead>
						<tbody className="divide-y divide-gray-200 bg-black dark:bg-black">
							{Object.entries(params).map(([key, val]) => (
								<tr key={key} className="hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors">
									<td className="px-4 py-3 font-medium text-gray-900 dark:text-white">{key}</td>
									<td className="px-4 py-3 text-gray-700 dark:text-gray-300">{val.toString()}</td>
									<td className="px-4 py-3">
										<Button
											variant="ghost"
											size="icon"
											className="text-red-600 hover:bg-red-50 dark:hover:bg-red-900/20 hover:text-red-700 dark:text-red-500"
											onClick={() => handleDelete(key)}
											aria-label={`Delete parameter ${key}`}
										>
											<Trash2 className="w-4 h-4" />
										</Button>
									</td>
								</tr>
							))}
						</tbody>
					</table>
				</div>
			)}
		</div>
	);
}
