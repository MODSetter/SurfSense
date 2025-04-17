import React from 'react';
import { Control } from 'react-hook-form';
import { FormField, FormItem, FormLabel, FormControl, FormDescription, FormMessage } from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { KeyRound } from 'lucide-react';

// Assuming EditConnectorFormValues is defined elsewhere or passed as generic
interface EditSimpleTokenFormProps {
    control: Control<any>;
    fieldName: string; // e.g., "SLACK_BOT_TOKEN"
    fieldLabel: string; // e.g., "Slack Bot Token"
    fieldDescription: string;
    placeholder?: string;
}

export function EditSimpleTokenForm({
    control,
    fieldName,
    fieldLabel,
    fieldDescription,
    placeholder
}: EditSimpleTokenFormProps) {
    return (
        <FormField
            control={control}
            name={fieldName}
            render={({ field }) => (
                <FormItem>
                    <FormLabel className="flex items-center gap-1"><KeyRound className="h-4 w-4" /> {fieldLabel}</FormLabel>
                    <FormControl><Input type="password" placeholder={placeholder} {...field} /></FormControl>
                    <FormDescription>{fieldDescription}</FormDescription>
                    <FormMessage />
                </FormItem>
            )}
        />
    );
} 
