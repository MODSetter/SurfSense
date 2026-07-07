"use client";
import { Check, ChevronsUpDown } from "lucide-react";
import { useMemo, useState } from "react";
import { Button } from "@/components/ui/button";
import {
	Command,
	CommandEmpty,
	CommandGroup,
	CommandInput,
	CommandItem,
	CommandList,
} from "@/components/ui/command";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { getTimezones } from "@/lib/automations/builder-schema";
import { cn } from "@/lib/utils";

interface TimezoneComboboxProps {
	value: string;
	onChange: (value: string) => void;
}

/**
 * Searchable IANA timezone picker. The full ``Intl.supportedValuesOf`` list is
 * long, so it lives behind a Command search instead of a flat Select.
 */
export function TimezoneCombobox({ value, onChange }: TimezoneComboboxProps) {
	const [open, setOpen] = useState(false);
	const timezones = useMemo(() => getTimezones(), []);

	return (
		<Popover open={open} onOpenChange={setOpen}>
			<PopoverTrigger asChild>
				<Button
					type="button"
					variant="outline"
					role="combobox"
					aria-expanded={open}
					className="w-full justify-between border-popover-border bg-transparent font-normal hover:bg-transparent"
				>
					<span className="truncate">{value || "Select timezone"}</span>
					<ChevronsUpDown className="ml-2 h-4 w-4 shrink-0 opacity-50" />
				</Button>
			</PopoverTrigger>
			<PopoverContent
				className="w-[calc(var(--radix-popover-trigger-width)/3)] min-w-72 max-w-[90vw] overflow-hidden border border-popover-border p-0"
				align="start"
			>
				<Command className="bg-popover">
					<CommandInput placeholder="Search timezone..." />
					<CommandList>
						<CommandEmpty>No timezone found.</CommandEmpty>
						<CommandGroup className="p-0">
							{timezones.map((tz) => (
								<CommandItem
									key={tz}
									value={tz}
									className="rounded-none px-3"
									onSelect={() => {
										onChange(tz);
										setOpen(false);
									}}
								>
									<Check
										className={cn("mr-2 h-4 w-4", value === tz ? "opacity-100" : "opacity-0")}
									/>
									{tz}
								</CommandItem>
							))}
						</CommandGroup>
					</CommandList>
				</Command>
			</PopoverContent>
		</Popover>
	);
}
