"use client";

import React, { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Badge } from '@/components/ui/badge';
import { Brain, Zap, Bot, AlertCircle, CheckCircle } from 'lucide-react';
import { useLLMConfigs, useLLMPreferences } from '@/hooks/use-llm-configs';
import { Alert, AlertDescription } from '@/components/ui/alert';

const ROLE_DESCRIPTIONS = {
  long_context: {
    icon: Brain,
    title: 'Long Context LLM',
    description: 'Handles complex tasks requiring extensive context understanding and reasoning',
    color: 'bg-blue-100 text-blue-800 border-blue-200',
    examples: 'Document analysis, research synthesis, complex Q&A'
  },
  fast: {
    icon: Zap,
    title: 'Fast LLM',
    description: 'Optimized for quick responses and real-time interactions',
    color: 'bg-green-100 text-green-800 border-green-200',
    examples: 'Quick searches, simple questions, instant responses'
  },
  strategic: {
    icon: Bot,
    title: 'Strategic LLM',
    description: 'Advanced reasoning for planning and strategic decision making',
    color: 'bg-purple-100 text-purple-800 border-purple-200',
    examples: 'Planning workflows, strategic analysis, complex problem solving'
  }
};

interface AssignRolesStepProps {
  onPreferencesUpdated?: () => Promise<void>;
}

export function AssignRolesStep({ onPreferencesUpdated }: AssignRolesStepProps) {
  const { llmConfigs } = useLLMConfigs();
  const { preferences, updatePreferences } = useLLMPreferences();
  

  const [assignments, setAssignments] = useState({
    long_context_llm_id: preferences.long_context_llm_id || '',
    fast_llm_id: preferences.fast_llm_id || '',
    strategic_llm_id: preferences.strategic_llm_id || ''
  });


  useEffect(() => {
    setAssignments({
      long_context_llm_id: preferences.long_context_llm_id || '',
      fast_llm_id: preferences.fast_llm_id || '',
      strategic_llm_id: preferences.strategic_llm_id || ''
    });
  }, [preferences]);

  const handleRoleAssignment = async (role: string, configId: string) => {
    const newAssignments = {
      ...assignments,
      [role]: configId === '' ? '' : parseInt(configId)
    };
    
    setAssignments(newAssignments);
    
    // Auto-save if this assignment completes all roles
    const hasAllAssignments = newAssignments.long_context_llm_id && newAssignments.fast_llm_id && newAssignments.strategic_llm_id;
    
    if (hasAllAssignments) {
      const numericAssignments = {
        long_context_llm_id: typeof newAssignments.long_context_llm_id === 'string' ? parseInt(newAssignments.long_context_llm_id) : newAssignments.long_context_llm_id,
        fast_llm_id: typeof newAssignments.fast_llm_id === 'string' ? parseInt(newAssignments.fast_llm_id) : newAssignments.fast_llm_id,
        strategic_llm_id: typeof newAssignments.strategic_llm_id === 'string' ? parseInt(newAssignments.strategic_llm_id) : newAssignments.strategic_llm_id,
      };
      
      const success = await updatePreferences(numericAssignments);
      
      // Refresh parent preferences state
      if (success && onPreferencesUpdated) {
        await onPreferencesUpdated();
      }
    }
  };



  const isAssignmentComplete = assignments.long_context_llm_id && assignments.fast_llm_id && assignments.strategic_llm_id;

  if (llmConfigs.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-12">
        <AlertCircle className="w-16 h-16 text-muted-foreground mb-4" />
        <h3 className="text-lg font-semibold mb-2">No LLM Configurations Found</h3>
        <p className="text-muted-foreground text-center">
          Please add at least one LLM provider in the previous step before assigning roles.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Info Alert */}
      <Alert>
        <AlertCircle className="h-4 w-4" />
        <AlertDescription>
          Assign your LLM configurations to specific roles. Each role serves different purposes in your workflow.
        </AlertDescription>
      </Alert>

      {/* Role Assignment Cards */}
      <div className="grid gap-6">
        {Object.entries(ROLE_DESCRIPTIONS).map(([key, role]) => {
          const IconComponent = role.icon;
          const currentAssignment = assignments[`${key}_llm_id` as keyof typeof assignments];
          const assignedConfig = llmConfigs.find(config => config.id === currentAssignment);
          
          return (
            <motion.div
              key={key}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: Object.keys(ROLE_DESCRIPTIONS).indexOf(key) * 0.1 }}
            >
              <Card className={`border-l-4 ${currentAssignment ? 'border-l-primary' : 'border-l-muted'}`}>
                <CardHeader className="pb-3">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <div className={`p-2 rounded-lg ${role.color}`}>
                        <IconComponent className="w-5 h-5" />
                      </div>
                      <div>
                        <CardTitle className="text-lg">{role.title}</CardTitle>
                        <CardDescription className="mt-1">{role.description}</CardDescription>
                      </div>
                    </div>
                    {currentAssignment && (
                      <CheckCircle className="w-5 h-5 text-green-500" />
                    )}
                  </div>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="text-sm text-muted-foreground">
                    <strong>Use cases:</strong> {role.examples}
                  </div>
                  
                  <div className="space-y-2">
                    <label className="text-sm font-medium">Assign LLM Configuration:</label>
                    <Select
                      value={currentAssignment?.toString() || ''}
                      onValueChange={(value) => handleRoleAssignment(`${key}_llm_id`, value)}
                    >
                      <SelectTrigger>
                        <SelectValue placeholder="Select an LLM configuration" />
                      </SelectTrigger>
                      <SelectContent>
                        {llmConfigs
                          .filter(config => config.id && config.id.toString().trim() !== '')
                          .map((config) => (
                            <SelectItem key={config.id} value={config.id.toString()}>
                              <div className="flex items-center gap-2">
                                <Badge variant="outline" className="text-xs">
                                  {config.provider}
                                </Badge>
                                <span>{config.name}</span>
                                <span className="text-muted-foreground">({config.model_name})</span>
                              </div>
                            </SelectItem>
                          ))}

                      </SelectContent>
                    </Select>
                  </div>

                  {assignedConfig && (
                    <div className="mt-3 p-3 bg-muted/50 rounded-lg">
                      <div className="flex items-center gap-2 text-sm">
                        <Bot className="w-4 h-4" />
                        <span className="font-medium">Assigned:</span>
                        <Badge variant="secondary">{assignedConfig.provider}</Badge>
                        <span>{assignedConfig.name}</span>
                      </div>
                      <div className="text-xs text-muted-foreground mt-1">
                        Model: {assignedConfig.model_name}
                      </div>
                    </div>
                  )}
                </CardContent>
              </Card>
            </motion.div>
          );
        })}
      </div>



      {/* Status Indicator */}
      {isAssignmentComplete && (
        <div className="flex justify-center pt-4">
          <div className="flex items-center gap-2 px-4 py-2 bg-green-50 text-green-700 rounded-lg border border-green-200">
            <CheckCircle className="w-4 h-4" />
            <span className="text-sm font-medium">All roles assigned and saved!</span>
          </div>
        </div>
      )}

      {/* Progress Indicator */}
      <div className="flex justify-center">
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <span>Progress:</span>
          <div className="flex gap-1">
            {Object.keys(ROLE_DESCRIPTIONS).map((key, index) => (
              <div
                key={key}
                className={`w-2 h-2 rounded-full ${
                  assignments[`${key}_llm_id` as keyof typeof assignments]
                    ? 'bg-primary'
                    : 'bg-muted'
                }`}
              />
            ))}
          </div>
          <span>
            {Object.values(assignments).filter(Boolean).length} of {Object.keys(ROLE_DESCRIPTIONS).length} roles assigned
          </span>
        </div>
      </div>
    </div>
  );
} 