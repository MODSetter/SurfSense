"use client";
// Example data from ShadCN: https://github.com/shadcn-ui/ui/blob/0fae3fd93ae749aca708bdfbbbeddc5d576bfb2e/apps/www/registry/default/example/cards/stats.tsx#L61

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Line, LineChart, ResponsiveContainer } from "recharts";
import { twColourConfig } from "@/lib/twConfig";

const data = [
  {
    revenue: 10400,
    subscription: 240,
  },
  {
    revenue: 14405,
    subscription: 300,
  },
  {
    revenue: 9400,
    subscription: 200,
  },
  {
    revenue: 8200,
    subscription: 278,
  },
  {
    revenue: 7000,
    subscription: 189,
  },
  {
    revenue: 9600,
    subscription: 239,
  },
  {
    revenue: 11244,
    subscription: 278,
  },
  {
    revenue: 26475,
    subscription: 189,
  },
];

export function DemoRevenue() {
  return (
    <Card className="w-full">
      <CardHeader className="flex flex-row justify-between space-y-0 pb-4">
        <CardTitle className="text-base font-normal">Total Revenue</CardTitle>
      </CardHeader>
      <CardContent className="text-left">
        <div className="text-2xl font-bold">$15,231.89</div>
        <p className="text-xs text-muted-foreground">+20.1% from last month</p>
        <div className="h-[140px]">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart
              data={data}
              margin={{
                top: 5,
                right: 10,
                left: 10,
                bottom: 0,
              }}
            >
              <Line
                type="monotone"
                strokeWidth={2}
                dataKey="revenue"
                activeDot={{
                  r: 6,
                  style: {
                    fill: `${twColourConfig.primary.DEFAULT}`,
                    opacity: 0.25,
                  },
                }}
                stroke={twColourConfig.primary.DEFAULT}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </CardContent>
    </Card>
  );
}
