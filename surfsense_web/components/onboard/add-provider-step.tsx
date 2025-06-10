"use client";

import React, { useState } from 'react';
import { motion } from 'framer-motion';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';

import { Badge } from '@/components/ui/badge';
import { Plus, Trash2, Bot, AlertCircle } from 'lucide-react';
import { useLLMConfigs, CreateLLMConfig } from '@/hooks/use-llm-configs';
import { toast } from 'sonner';
import { Alert, AlertDescription } from '@/components/ui/alert';

const LLM_PROVIDERS = [
  { value: 'OPENAI', label: 'OpenAI', example: 'gpt-4o, gpt-4, gpt-3.5-turbo' },
  { value: 'ANTHROPIC', label: 'Anthropic', example: 'claude-3-5-sonnet-20241022, claude-3-opus-20240229' },
  { value: 'GROQ', label: 'Groq', example: 'llama3-70b-8192, mixtral-8x7b-32768' },
  { value: 'COHERE', label: 'Cohere', example: 'command-r-plus, command-r' },
  { value: 'HUGGINGFACE', label: 'HuggingFace', example: 'microsoft/DialoGPT-medium' },
  { value: 'AZURE_OPENAI', label: 'Azure OpenAI', example: 'gpt-4, gpt-35-turbo' },
  { value: 'GOOGLE', label: 'Google', example: 'gemini-pro, gemini-pro-vision' },
  { value: 'AWS_BEDROCK', label: 'AWS Bedrock', example: 'anthropic.claude-v2' },
  { value: 'OLLAMA', label: 'Ollama', example: 'llama2, codellama' },
  { value: 'MISTRAL', label: 'Mistral', example: 'mistral-large-latest, mistral-medium' },
  { value: 'TOGETHER_AI', label: 'Together AI', example: 'togethercomputer/llama-2-70b-chat' },
  { value: 'REPLICATE', label: 'Replicate', example: 'meta/llama-2-70b-chat' },
  { value: 'CUSTOM', label: 'Custom Provider', example: 'your-custom-model' },
];

interface AddProviderStepProps {
  onConfigCreated?: () => void;
  onConfigDeleted?: () => void;
}

export function AddProviderStep({ onConfigCreated, onConfigDeleted }: AddProviderStepProps) {
  const { llmConfigs, createLLMConfig, deleteLLMConfig } = useLLMConfigs();
  const [isAddingNew, setIsAddingNew] = useState(false);
  const [formData, setFormData] = useState<CreateLLMConfig>({
    name: '',
    provider: '',
    custom_provider: '',
    model_name: '',
    api_key: '',
    api_base: '',
    litellm_params: {}
  });
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleInputChange = (field: keyof CreateLLMConfig, value: string) => {
    setFormData(prev => ({ ...prev, [field]: value }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!formData.name || !formData.provider || !formData.model_name || !formData.api_key) {
      toast.error('Please fill in all required fields');
      return;
    }

    setIsSubmitting(true);
    const result = await createLLMConfig(formData);
    setIsSubmitting(false);

    if (result) {
      setFormData({
        name: '',
        provider: '',
        custom_provider: '',
        model_name: '',
        api_key: '',
        api_base: '',
        litellm_params: {}
      });
      setIsAddingNew(false);
      // Notify parent component that a config was created
      onConfigCreated?.();
    }
  };

  const selectedProvider = LLM_PROVIDERS.find(p => p.value === formData.provider);

  return (
    <div className="space-y-6">
      {/* Info Alert */}
      <Alert>
        <AlertCircle className="h-4 w-4" />
        <AlertDescription>
          Add at least one LLM provider to continue. You can configure multiple providers and choose specific roles for each one in the next step.
        </AlertDescription>
      </Alert>

      {/* Existing Configurations */}
      {llmConfigs.length > 0 && (
        <div className="space-y-4">
          <h3 className="text-lg font-semibold">Your LLM Configurations</h3>
          <div className="grid gap-4">
            {llmConfigs.map((config) => (
              <motion.div
                key={config.id}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -10 }}
              >
                <Card className="border-l-4 border-l-primary">
                  <CardContent className="pt-4">
                    <div className="flex items-center justify-between">
                      <div className="flex-1">
                        <div className="flex items-center gap-2 mb-2">
                          <Bot className="w-4 h-4" />
                          <h4 className="font-medium">{config.name}</h4>
                          <Badge variant="secondary">{config.provider}</Badge>
                        </div>
                        <p className="text-sm text-muted-foreground">
                          Model: {config.model_name}
                          {config.api_base && ` • Base: ${config.api_base}`}
                        </p>
                      </div>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={async () => {
                          const success = await deleteLLMConfig(config.id);
                          if (success) {
                            onConfigDeleted?.();
                          }
                        }}
                        className="text-destructive hover:text-destructive"
                      >
                        <Trash2 className="w-4 h-4" />
                      </Button>
                    </div>
                  </CardContent>
                </Card>
              </motion.div>
            ))}
          </div>
        </div>
      )}

      {/* Add New Provider */}
      {!isAddingNew ? (
        <Card className="border-dashed border-2 hover:border-primary/50 transition-colors">
          <CardContent className="flex flex-col items-center justify-center py-12">
            <Plus className="w-12 h-12 text-muted-foreground mb-4" />
            <h3 className="text-lg font-semibold mb-2">Add LLM Provider</h3>
            <p className="text-muted-foreground text-center mb-4">
              Configure your first model provider to get started
            </p>
            <Button onClick={() => setIsAddingNew(true)}>
              <Plus className="w-4 h-4 mr-2" />
              Add Provider
            </Button>
          </CardContent>
        </Card>
      ) : (
        <Card>
          <CardHeader>
            <CardTitle>Add New LLM Provider</CardTitle>
            <CardDescription>
              Configure a new language model provider for your AI assistant
            </CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleSubmit} className="space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="name">Configuration Name *</Label>
                  <Input
                    id="name"
                    placeholder="e.g., My OpenAI GPT-4"
                    value={formData.name}
                    onChange={(e) => handleInputChange('name', e.target.value)}
                    required
                  />
                </div>

                <div className="space-y-2">
                  <Label htmlFor="provider">Provider *</Label>
                  <Select value={formData.provider} onValueChange={(value) => handleInputChange('provider', value)}>
                    <SelectTrigger>
                      <SelectValue placeholder="Select a provider" />
                    </SelectTrigger>
                    <SelectContent>
                      {LLM_PROVIDERS.map((provider) => (
                        <SelectItem key={provider.value} value={provider.value}>
                          {provider.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </div>

              {formData.provider === 'CUSTOM' && (
                <div className="space-y-2">
                  <Label htmlFor="custom_provider">Custom Provider Name *</Label>
                  <Input
                    id="custom_provider"
                    placeholder="e.g., my-custom-provider"
                    value={formData.custom_provider}
                    onChange={(e) => handleInputChange('custom_provider', e.target.value)}
                    required
                  />
                </div>
              )}

              <div className="space-y-2">
                <Label htmlFor="model_name">Model Name *</Label>
                <Input
                  id="model_name"
                  placeholder={selectedProvider?.example || "e.g., gpt-4"}
                  value={formData.model_name}
                  onChange={(e) => handleInputChange('model_name', e.target.value)}
                  required
                />
                {selectedProvider && (
                  <p className="text-xs text-muted-foreground">
                    Examples: {selectedProvider.example}
                  </p>
                )}
              </div>

              <div className="space-y-2">
                <Label htmlFor="api_key">API Key *</Label>
                <Input
                  id="api_key"
                  type="password"
                  placeholder="Your API key"
                  value={formData.api_key}
                  onChange={(e) => handleInputChange('api_key', e.target.value)}
                  required
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="api_base">API Base URL (Optional)</Label>
                <Input
                  id="api_base"
                  placeholder="e.g., https://api.openai.com/v1"
                  value={formData.api_base}
                  onChange={(e) => handleInputChange('api_base', e.target.value)}
                />
              </div>

              <div className="flex gap-2 pt-4">
                <Button type="submit" disabled={isSubmitting}>
                  {isSubmitting ? 'Adding...' : 'Add Provider'}
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => setIsAddingNew(false)}
                  disabled={isSubmitting}
                >
                  Cancel
                </Button>
              </div>
            </form>
          </CardContent>
        </Card>
      )}
    </div>
  );
} 