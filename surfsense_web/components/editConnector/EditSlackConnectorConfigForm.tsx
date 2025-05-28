import React, { useState, useEffect } from 'react';
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Checkbox } from "@/components/ui/checkbox";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { SearchSourceConnector } from '@/hooks/useSearchSourceConnectors'; // Adjust path as per your project structure
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'; // For grouping

interface EditSlackConnectorConfigFormProps {
  connector: SearchSourceConnector;
  onConfigChange: (newConfig: Record<string, any>) => void;
  disabled: boolean;
}

const EditSlackConnectorConfigForm: React.FC<EditSlackConnectorConfigFormProps> = ({
  connector,
  onConfigChange,
  disabled,
}) => {
  const [currentConfig, setCurrentConfig] = useState<Record<string, any>>(connector.config || {});

  useEffect(() => {
    // Initialize with default values for new fields if they don't exist in the connector's config
    const initialConfig = {
      SLACK_BOT_TOKEN: '',
      slack_membership_filter_type: 'all_member_channels',
      slack_selected_channel_ids: [], // Placeholder, managed elsewhere
      slack_initial_indexing_days: 30,
      slack_initial_max_messages_per_channel: 1000,
      slack_periodic_indexing_enabled: false,
      slack_periodic_indexing_frequency: 'daily',
      slack_max_messages_per_channel_periodic: 100,
      ...connector.config, // Override defaults with existing config
    };
    setCurrentConfig(initialConfig);
    // Optionally, call onConfigChange here if you want to ensure parent is updated with defaults
    // onConfigChange(initialConfig); 
  }, [connector.config]);

  const handleChange = (key: string, value: any) => {
    const newConfig = { ...currentConfig, [key]: value };
    // Special handling for slack_initial_indexing_days and slack_initial_max_messages_per_channel
    // to ensure they are numbers if not empty, or specific allowed values like -1 for days
    if (key === 'slack_initial_indexing_days' || key === 'slack_initial_max_messages_per_channel' || key === 'slack_max_messages_per_channel_periodic') {
        if (value === '' || value === null) {
            newConfig[key] = null; // Or some default like 0 or -1 depending on desired behavior for empty
        } else {
            const numValue = parseInt(value, 10);
            newConfig[key] = isNaN(numValue) ? null : numValue; // Store as number or null if not a valid number
        }
    }
    setCurrentConfig(newConfig);
    onConfigChange(newConfig);
  };
  
  const handleCheckboxChange = (key: string, checked: boolean) => {
    const newConfig = { ...currentConfig, [key]: checked };
    setCurrentConfig(newConfig);
    onConfigChange(newConfig);
  };

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle>Authentication</CardTitle>
          <CardDescription>Configure your Slack Bot Token.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="slack-bot-token">Slack Bot Token</Label>
            <Input
              id="slack-bot-token"
              type="password" // Use password type for sensitive tokens
              value={currentConfig.SLACK_BOT_TOKEN || ''}
              onChange={(e) => handleChange('SLACK_BOT_TOKEN', e.target.value)}
              disabled={disabled}
              placeholder="xoxb-..."
            />
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Initial Indexing Settings</CardTitle>
          <CardDescription>Control how SurfSense initially syncs messages from Slack.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="slack-membership-filter-type">Channel Indexing Behavior</Label>
            <Select
              value={currentConfig.slack_membership_filter_type || 'all_member_channels'}
              onValueChange={(value) => handleChange('slack_membership_filter_type', value)}
              disabled={disabled}
            >
              <SelectTrigger id="slack-membership-filter-type">
                <SelectValue placeholder="Select behavior" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all_member_channels">Index All Channels Where Bot is Member</SelectItem>
                <SelectItem value="selected_member_channels">Index Only Selected Channels</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-2">
            <Label>Selected Channels</Label>
            <p className="text-sm text-muted-foreground">
              Channel selection is managed in the 'Channels' tab after saving this basic configuration.
            </p>
          </div>
          
          <div className="space-y-2">
            <Label htmlFor="slack-initial-indexing-days">Initial Indexing Period (days)</Label>
            <Input
              id="slack-initial-indexing-days"
              type="number"
              value={currentConfig.slack_initial_indexing_days === null || currentConfig.slack_initial_indexing_days === undefined ? '' : currentConfig.slack_initial_indexing_days}
              onChange={(e) => handleChange('slack_initial_indexing_days', e.target.value)}
              disabled={disabled}
              placeholder="-1 for all time"
            />
            <p className="text-sm text-muted-foreground">
              Enter -1 for all time, 0 for no initial history, or a positive number for specific days.
            </p>
          </div>

          <div className="space-y-2">
            <Label htmlFor="slack-initial-max-messages-per-channel">Max Messages Per Channel (Initial Sync)</Label>
            <Input
              id="slack-initial-max-messages-per-channel"
              type="number"
              value={currentConfig.slack_initial_max_messages_per_channel === null || currentConfig.slack_initial_max_messages_per_channel === undefined ? '' : currentConfig.slack_initial_max_messages_per_channel}
              onChange={(e) => handleChange('slack_initial_max_messages_per_channel', e.target.value)}
              disabled={disabled}
              placeholder="e.g., 1000"
            />
          </div>
        </CardContent>
      </Card>
      
      <Card>
        <CardHeader>
          <CardTitle>Periodic Indexing Settings</CardTitle>
          <CardDescription>Configure automatic background syncing for new messages.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center space-x-2">
            <Checkbox
              id="slack-periodic-indexing-enabled"
              checked={!!currentConfig.slack_periodic_indexing_enabled}
              onCheckedChange={(checked) => handleCheckboxChange('slack_periodic_indexing_enabled', !!checked)}
              disabled={disabled}
            />
            <Label htmlFor="slack-periodic-indexing-enabled" className="font-medium">
              Enable Periodic Indexing
            </Label>
          </div>

          {currentConfig.slack_periodic_indexing_enabled && (
            <>
              <div className="space-y-2 pl-6"> {/* Indent options for enabled periodic indexing */}
                <Label htmlFor="slack-periodic-indexing-frequency">Periodic Indexing Frequency</Label>
                <Select
                  value={currentConfig.slack_periodic_indexing_frequency || 'daily'}
                  onValueChange={(value) => handleChange('slack_periodic_indexing_frequency', value)}
                  disabled={disabled || !currentConfig.slack_periodic_indexing_enabled}
                >
                  <SelectTrigger id="slack-periodic-indexing-frequency">
                    <SelectValue placeholder="Select frequency" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="daily">Daily</SelectItem>
                    <SelectItem value="weekly">Weekly</SelectItem>
                    <SelectItem value="monthly">Monthly</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-2 pl-6">
                <Label htmlFor="slack-max-messages-per-channel-periodic">Max Messages Per Channel (Periodic Sync)</Label>
                <Input
                  id="slack-max-messages-per-channel-periodic"
                  type="number"
                  value={currentConfig.slack_max_messages_per_channel_periodic === null || currentConfig.slack_max_messages_per_channel_periodic === undefined ? '' : currentConfig.slack_max_messages_per_channel_periodic}
                  onChange={(e) => handleChange('slack_max_messages_per_channel_periodic', e.target.value)}
                  disabled={disabled || !currentConfig.slack_periodic_indexing_enabled}
                  placeholder="e.g., 100"
                />
              </div>
            </>
          )}
        </CardContent>
      </Card>
    </div>
  );
};

export default EditSlackConnectorConfigForm;
</>
