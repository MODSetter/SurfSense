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
					className="w-full justify-between font-normal"
				>
					<span className="truncate">{value || "Select timezone"}</span>
					<ChevronsUpDown className="ml-2 h-4 w-4 shrink-0 opacity-50" />
				</Button>
			</PopoverTrigger>
			<PopoverContent className="w-[--radix-popover-trigger-width] p-0" align="start">
				<Command>
					<CommandInput placeholder="Search timezone..." />
					<CommandList>
						<CommandEmpty>No timezone found.</CommandEmpty>
						<CommandGroup>
							{timezones.map((tz) => (
								<CommandItem
									key={tz}
									value={tz}
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
