"use client";

import { useState, useEffect, useId } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { 
  Table, 
  TableBody, 
  TableCell, 
  TableHead, 
  TableHeader, 
  TableRow 
} from "@/components/ui/table";
import { 
  Dialog, 
  DialogContent, 
  DialogDescription, 
  DialogHeader, 
  DialogTitle, 
  DialogTrigger 
} from "@/components/ui/dialog";
import { 
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { 
  Clock, 
  Calendar, 
  Play, 
  Pause, 
  Settings, 
  Plus,
  RefreshCw,
  CheckCircle,
  XCircle,
  AlertCircle
} from "lucide-react";
import { toast } from "sonner";
import { format } from "date-fns";

interface Connector {
  id: number;
  name: string;
  connector_type: string;
  is_indexable: boolean;
}

interface ConnectorSchedule {
  id: number;
  connector_id: number;
  search_space_id: number;
  schedule_type: "HOURLY" | "DAILY" | "WEEKLY" | "CUSTOM";
  cron_expression?: string;
  is_active: boolean;
  last_run_at?: string;
  next_run_at?: string;
  connector?: Connector;
}

interface SchedulerStatus {
  running: boolean;
  active_jobs: number;
  max_concurrent_jobs: number;
  check_interval: number;
}

export default function ConnectorSchedulesPage({
  params,
}: {
  params: Promise<{ search_space_id: string }>;
}) {
  const isActiveSwitchId = useId();
  const [searchSpaceId, setSearchSpaceId] = useState<string>("");
  const [schedules, setSchedules] = useState<ConnectorSchedule[]>([]);
  const [connectors, setConnectors] = useState<Connector[]>([]);
  const [schedulerStatus, setSchedulerStatus] = useState<SchedulerStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [isCreateDialogOpen, setIsCreateDialogOpen] = useState(false);
  const [newSchedule, setNewSchedule] = useState({
    connector_id: "",
    schedule_type: "DAILY" as const,
    cron_expression: "",
    daily_time: "02:00",
    weekly_day: "6",
    weekly_time: "02:00",
    hourly_minute: "0",
    is_active: true,
  });

  useEffect(() => {
    const resolveParams = async () => {
      const resolved = await params;
      setSearchSpaceId(resolved.search_space_id);
    };
    resolveParams();
  }, [params]);

  useEffect(() => {
    if (searchSpaceId) {
      setLoading(true);
      Promise.all([
        fetchSchedules(),
        fetchConnectors(),
        fetchSchedulerStatus()
      ]).finally(() => {
        setLoading(false);
      });
    }
  }, [searchSpaceId]);

  const fetchSchedules = async () => {
    try {
      const response = await fetch(`/api/v1/connector-schedules/?search_space_id=${searchSpaceId}`);
      if (response.ok) {
        const data = await response.json();
        setSchedules(data);
      }
    } catch (error) {
      console.error("Failed to fetch schedules:", error);
      toast.error("Failed to fetch schedules");
    }
  };

  const fetchConnectors = async () => {
    try {
      const response = await fetch("/api/v1/search-source-connectors/");
      if (response.ok) {
        const data = await response.json();
        // Filter only indexable connectors
        setConnectors(data.filter((c: Connector) => c.is_indexable));
      }
    } catch (error) {
      console.error("Failed to fetch connectors:", error);
      toast.error("Failed to fetch connectors");
    }
  };

  const fetchSchedulerStatus = async () => {
    try {
      const response = await fetch("/api/v1/scheduler/status");
      if (response.ok) {
        const data = await response.json();
        setSchedulerStatus(data);
      }
    } catch (error) {
      console.error("Failed to fetch scheduler status:", error);
    }
  };

  const createSchedule = async () => {
    try {
      const scheduleData = {
        connector_id: parseInt(newSchedule.connector_id),
        search_space_id: parseInt(searchSpaceId),
        schedule_type: newSchedule.schedule_type,
        cron_expression: newSchedule.schedule_type === "CUSTOM" ? newSchedule.cron_expression : undefined,
        daily_time: newSchedule.schedule_type === "DAILY" ? newSchedule.daily_time : undefined,
        weekly_day: newSchedule.schedule_type === "WEEKLY" ? parseInt(newSchedule.weekly_day) : undefined,
        weekly_time: newSchedule.schedule_type === "WEEKLY" ? newSchedule.weekly_time : undefined,
        hourly_minute: newSchedule.schedule_type === "HOURLY" ? parseInt(newSchedule.hourly_minute) : undefined,
        is_active: newSchedule.is_active,
      };

      const response = await fetch("/api/v1/connector-schedules/", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(scheduleData),
      });

      if (response.ok) {
        toast.success("Schedule created successfully");
        setIsCreateDialogOpen(false);
        setNewSchedule({
          connector_id: "",
          schedule_type: "DAILY",
          cron_expression: "",
          daily_time: "02:00",
          weekly_day: "6",
          weekly_time: "02:00",
          hourly_minute: "0",
          is_active: true,
        });
        fetchSchedules();
      } else {
        const error = await response.json();
        toast.error(error.detail || "Failed to create schedule");
      }
    } catch (error) {
      console.error("Failed to create schedule:", error);
      toast.error("Failed to create schedule");
    }
  };

  const toggleSchedule = async (scheduleId: number, isActive: boolean) => {
    try {
      const response = await fetch(`/api/v1/connector-schedules/${scheduleId}`, {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ is_active: !isActive }),
      });

      if (response.ok) {
        toast.success(`Schedule ${!isActive ? "activated" : "deactivated"}`);
        fetchSchedules();
      } else {
        toast.error("Failed to update schedule");
      }
    } catch (error) {
      console.error("Failed to toggle schedule:", error);
      toast.error("Failed to update schedule");
    }
  };

  const forceExecuteSchedule = async (scheduleId: number) => {
    try {
      const response = await fetch(`/api/v1/scheduler/schedules/${scheduleId}/force-execute`, {
        method: "POST",
      });

      if (response.ok) {
        toast.success("Schedule execution started");
        fetchSchedules();
      } else {
        toast.error("Failed to execute schedule");
      }
    } catch (error) {
      console.error("Failed to execute schedule:", error);
      toast.error("Failed to execute schedule");
    }
  };

  const getScheduleTypeIcon = (type: string) => {
    switch (type) {
      case "HOURLY":
        return <Clock className="h-4 w-4" />;
      case "DAILY":
        return <Calendar className="h-4 w-4" />;
      case "WEEKLY":
        return <Calendar className="h-4 w-4" />;
      case "CUSTOM":
        return <Settings className="h-4 w-4" />;
      default:
        return <Clock className="h-4 w-4" />;
    }
  };

  const getScheduleTypeLabel = (type: string) => {
    switch (type) {
      case "HOURLY":
        return "Hourly";
      case "DAILY":
        return "Daily";
      case "WEEKLY":
        return "Weekly";
      case "CUSTOM":
        return "Custom";
      default:
        return type;
    }
  };

  const getConnectorName = (connectorId: number) => {
    const connector = connectors.find(c => c.id === connectorId);
    return connector?.name || `Connector ${connectorId}`;
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <RefreshCw className="h-8 w-8 animate-spin" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Connector Schedules</h1>
          <p className="text-muted-foreground">
            Automate your connector syncs with scheduled indexing
          </p>
        </div>
        
        <Dialog open={isCreateDialogOpen} onOpenChange={setIsCreateDialogOpen}>
          <DialogTrigger asChild>
            <Button>
              <Plus className="h-4 w-4 mr-2" />
              Create Schedule
            </Button>
          </DialogTrigger>
          <DialogContent className="sm:max-w-[500px]">
            <DialogHeader>
              <DialogTitle>Create New Schedule</DialogTitle>
              <DialogDescription>
                Set up automated syncing for your connectors
              </DialogDescription>
            </DialogHeader>
            <div className="space-y-4">
              <div>
                <Label htmlFor="connector">Connector</Label>
                <Select 
                  value={newSchedule.connector_id} 
                  onValueChange={(value) => setNewSchedule({ ...newSchedule, connector_id: value })}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Select a connector" />
                  </SelectTrigger>
                  <SelectContent>
                    {connectors.map((connector) => (
                      <SelectItem key={connector.id} value={connector.id.toString()}>
                        {connector.name} ({connector.connector_type})
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div>
                <Label htmlFor="schedule_type">Schedule Type</Label>
                <Select 
                  value={newSchedule.schedule_type} 
                  onValueChange={(value: any) => setNewSchedule({ ...newSchedule, schedule_type: value })}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="HOURLY">Hourly</SelectItem>
                    <SelectItem value="DAILY">Daily</SelectItem>
                    <SelectItem value="WEEKLY">Weekly</SelectItem>
                    <SelectItem value="CUSTOM">Custom (Cron)</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              {newSchedule.schedule_type === "DAILY" && (
                <div>
                  <Label htmlFor="daily_time">Time</Label>
                  <Input
                    type="time"
                    value={newSchedule.daily_time}
                    onChange={(e) => setNewSchedule({ ...newSchedule, daily_time: e.target.value })}
                  />
                </div>
              )}

              {newSchedule.schedule_type === "WEEKLY" && (
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <Label htmlFor="weekly_day">Day of Week</Label>
                    <Select 
                      value={newSchedule.weekly_day} 
                      onValueChange={(value) => setNewSchedule({ ...newSchedule, weekly_day: value })}
                    >
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="0">Monday</SelectItem>
                        <SelectItem value="1">Tuesday</SelectItem>
                        <SelectItem value="2">Wednesday</SelectItem>
                        <SelectItem value="3">Thursday</SelectItem>
                        <SelectItem value="4">Friday</SelectItem>
                        <SelectItem value="5">Saturday</SelectItem>
                        <SelectItem value="6">Sunday</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  <div>
                    <Label htmlFor="weekly_time">Time</Label>
                    <Input
                      type="time"
                      value={newSchedule.weekly_time}
                      onChange={(e) => setNewSchedule({ ...newSchedule, weekly_time: e.target.value })}
                    />
                  </div>
                </div>
              )}

              {newSchedule.schedule_type === "HOURLY" && (
                <div>
                  <Label htmlFor="hourly_minute">Minute (0-59)</Label>
                  <Input
                    type="number"
                    min="0"
                    max="59"
                    value={newSchedule.hourly_minute}
                    onChange={(e) => setNewSchedule({ ...newSchedule, hourly_minute: e.target.value })}
                  />
                </div>
              )}

              {newSchedule.schedule_type === "CUSTOM" && (
                <div>
                  <Label htmlFor="cron_expression">Cron Expression</Label>
                  <Input
                    placeholder="0 2 * * *"
                    value={newSchedule.cron_expression}
                    onChange={(e) => setNewSchedule({ ...newSchedule, cron_expression: e.target.value })}
                  />
                </div>
              )}

              <div className="flex items-center space-x-2">
                <Switch
                  id={isActiveSwitchId}
                  checked={newSchedule.is_active}
                  onCheckedChange={(checked) => setNewSchedule({ ...newSchedule, is_active: checked })}
                />
                <Label htmlFor={isActiveSwitchId}>Active</Label>
              </div>

              <div className="flex justify-end space-x-2">
                <Button variant="outline" onClick={() => setIsCreateDialogOpen(false)}>
                  Cancel
                </Button>
                <Button onClick={createSchedule}>
                  Create Schedule
                </Button>
              </div>
            </div>
          </DialogContent>
        </Dialog>
      </div>

      {/* Scheduler Status */}
      {schedulerStatus && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Settings className="h-5 w-5" />
              Scheduler Status
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
              <div className="text-center">
                <div className="text-2xl font-bold">
                  {schedulerStatus.running ? (
                    <CheckCircle className="h-8 w-8 text-green-500 mx-auto" />
                  ) : (
                    <XCircle className="h-8 w-8 text-red-500 mx-auto" />
                  )}
                </div>
                <p className="text-sm text-muted-foreground">Status</p>
              </div>
              <div className="text-center">
                <div className="text-2xl font-bold">{schedulerStatus.active_jobs}</div>
                <p className="text-sm text-muted-foreground">Active Jobs</p>
              </div>
              <div className="text-center">
                <div className="text-2xl font-bold">{schedulerStatus.max_concurrent_jobs}</div>
                <p className="text-sm text-muted-foreground">Max Concurrent</p>
              </div>
              <div className="text-center">
                <div className="text-2xl font-bold">{schedulerStatus.check_interval}s</div>
                <p className="text-sm text-muted-foreground">Check Interval</p>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Schedules Table */}
      <Card>
        <CardHeader>
          <CardTitle>Scheduled Connectors</CardTitle>
          <CardDescription>
            Manage automated sync schedules for your connectors
          </CardDescription>
        </CardHeader>
        <CardContent>
          {schedules.length === 0 ? (
            <div className="text-center py-8">
              <Calendar className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
              <h3 className="text-lg font-semibold">No schedules configured</h3>
              <p className="text-muted-foreground mb-4">
                Create your first schedule to automate connector syncing
              </p>
              <Button onClick={() => setIsCreateDialogOpen(true)}>
                <Plus className="h-4 w-4 mr-2" />
                Create Schedule
              </Button>
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Connector</TableHead>
                  <TableHead>Schedule</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Last Run</TableHead>
                  <TableHead>Next Run</TableHead>
                  <TableHead>Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {schedules.map((schedule) => (
                  <TableRow key={schedule.id}>
                    <TableCell className="font-medium">
                      {getConnectorName(schedule.connector_id)}
                    </TableCell>
                    <TableCell>
                      <div className="flex items-center gap-2">
                        {getScheduleTypeIcon(schedule.schedule_type)}
                        <span>{getScheduleTypeLabel(schedule.schedule_type)}</span>
                        {schedule.cron_expression && (
                          <Badge variant="outline" className="text-xs">
                            {schedule.cron_expression}
                          </Badge>
                        )}
                      </div>
                    </TableCell>
                    <TableCell>
                      <Badge variant={schedule.is_active ? "default" : "secondary"}>
                        {schedule.is_active ? "Active" : "Inactive"}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      {schedule.last_run_at ? (
                        <span className="text-sm">
                          {format(new Date(schedule.last_run_at), "MMM d, HH:mm")}
                        </span>
                      ) : (
                        <span className="text-muted-foreground">Never</span>
                      )}
                    </TableCell>
                    <TableCell>
                      {schedule.next_run_at ? (
                        <span className="text-sm">
                          {format(new Date(schedule.next_run_at), "MMM d, HH:mm")}
                        </span>
                      ) : (
                        <span className="text-muted-foreground">-</span>
                      )}
                    </TableCell>
                    <TableCell>
                      <div className="flex items-center gap-2">
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => toggleSchedule(schedule.id, schedule.is_active)}
                        >
                          {schedule.is_active ? <Pause className="h-4 w-4" /> : <Play className="h-4 w-4" />}
                        </Button>
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => forceExecuteSchedule(schedule.id)}
                          disabled={!schedule.is_active}
                        >
                          <RefreshCw className="h-4 w-4" />
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
