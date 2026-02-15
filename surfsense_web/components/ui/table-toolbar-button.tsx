'use client';

import * as React from 'react';

import type { DropdownMenuProps } from '@radix-ui/react-dropdown-menu';

import { TablePlugin, useTableMergeState } from '@platejs/table/react';
import {
  ArrowDown,
  ArrowLeft,
  ArrowRight,
  ArrowUp,
  Combine,
  Grid3x3Icon,
  Table,
  Trash2Icon,
  Ungroup,
  XIcon,
} from 'lucide-react';
import { KEYS } from 'platejs';
import { useEditorPlugin, useEditorSelector } from 'platejs/react';

import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuSub,
  DropdownMenuSubContent,
  DropdownMenuSubTrigger,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { cn } from '@/lib/utils';

import { ToolbarButton } from './toolbar';

export function TableToolbarButton(props: DropdownMenuProps) {
  const tableSelected = useEditorSelector(
    (editor) => editor.api.some({ match: { type: KEYS.table } }),
    []
  );

  const { editor, tf } = useEditorPlugin(TablePlugin);
  const [open, setOpen] = React.useState(false);
  const mergeState = useTableMergeState();

  return (
    <DropdownMenu open={open} onOpenChange={setOpen} modal={false} {...props}>
      <DropdownMenuTrigger asChild>
        <ToolbarButton pressed={open} tooltip="Table" isDropdown>
          <Table />
        </ToolbarButton>
      </DropdownMenuTrigger>

      <DropdownMenuContent
        className="flex w-[180px] min-w-0 flex-col"
        align="start"
      >
        <DropdownMenuGroup>
          <DropdownMenuSub>
            <DropdownMenuSubTrigger className="gap-2 data-[disabled]:pointer-events-none data-[disabled]:opacity-50">
              <Grid3x3Icon className="size-4" />
              <span>Table</span>
            </DropdownMenuSubTrigger>
            <DropdownMenuSubContent className="m-0 p-0">
              <TablePicker />
            </DropdownMenuSubContent>
          </DropdownMenuSub>

          <DropdownMenuSub>
            <DropdownMenuSubTrigger
              className="gap-2 data-[disabled]:pointer-events-none data-[disabled]:opacity-50"
              disabled={!tableSelected}
            >
              <div className="size-4" />
              <span>Cell</span>
            </DropdownMenuSubTrigger>
            <DropdownMenuSubContent>
              <DropdownMenuItem
                className="min-w-[180px]"
                disabled={!mergeState.canMerge}
                onSelect={() => {
                  tf.table.merge();
                  editor.tf.focus();
                }}
              >
                <Combine />
                Merge cells
              </DropdownMenuItem>
              <DropdownMenuItem
                className="min-w-[180px]"
                disabled={!mergeState.canSplit}
                onSelect={() => {
                  tf.table.split();
                  editor.tf.focus();
                }}
              >
                <Ungroup />
                Split cell
              </DropdownMenuItem>
            </DropdownMenuSubContent>
          </DropdownMenuSub>

          <DropdownMenuSub>
            <DropdownMenuSubTrigger
              className="gap-2 data-[disabled]:pointer-events-none data-[disabled]:opacity-50"
              disabled={!tableSelected}
            >
              <div className="size-4" />
              <span>Row</span>
            </DropdownMenuSubTrigger>
            <DropdownMenuSubContent>
              <DropdownMenuItem
                className="min-w-[180px]"
                disabled={!tableSelected}
                onSelect={() => {
                  tf.insert.tableRow({ before: true });
                  editor.tf.focus();
                }}
              >
                <ArrowUp />
                Insert row before
              </DropdownMenuItem>
              <DropdownMenuItem
                className="min-w-[180px]"
                disabled={!tableSelected}
                onSelect={() => {
                  tf.insert.tableRow();
                  editor.tf.focus();
                }}
              >
                <ArrowDown />
                Insert row after
              </DropdownMenuItem>
              <DropdownMenuItem
                className="min-w-[180px]"
                disabled={!tableSelected}
                onSelect={() => {
                  tf.remove.tableRow();
                  editor.tf.focus();
                }}
              >
                <XIcon />
                Delete row
              </DropdownMenuItem>
            </DropdownMenuSubContent>
          </DropdownMenuSub>

          <DropdownMenuSub>
            <DropdownMenuSubTrigger
              className="gap-2 data-[disabled]:pointer-events-none data-[disabled]:opacity-50"
              disabled={!tableSelected}
            >
              <div className="size-4" />
              <span>Column</span>
            </DropdownMenuSubTrigger>
            <DropdownMenuSubContent>
              <DropdownMenuItem
                className="min-w-[180px]"
                disabled={!tableSelected}
                onSelect={() => {
                  tf.insert.tableColumn({ before: true });
                  editor.tf.focus();
                }}
              >
                <ArrowLeft />
                Insert column before
              </DropdownMenuItem>
              <DropdownMenuItem
                className="min-w-[180px]"
                disabled={!tableSelected}
                onSelect={() => {
                  tf.insert.tableColumn();
                  editor.tf.focus();
                }}
              >
                <ArrowRight />
                Insert column after
              </DropdownMenuItem>
              <DropdownMenuItem
                className="min-w-[180px]"
                disabled={!tableSelected}
                onSelect={() => {
                  tf.remove.tableColumn();
                  editor.tf.focus();
                }}
              >
                <XIcon />
                Delete column
              </DropdownMenuItem>
            </DropdownMenuSubContent>
          </DropdownMenuSub>

          <DropdownMenuItem
            className="min-w-[180px]"
            disabled={!tableSelected}
            onSelect={() => {
              tf.remove.table();
              editor.tf.focus();
            }}
          >
            <Trash2Icon />
            Delete table
          </DropdownMenuItem>
        </DropdownMenuGroup>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

function TablePicker() {
  const { editor, tf } = useEditorPlugin(TablePlugin);

  const [tablePicker, setTablePicker] = React.useState({
    grid: Array.from({ length: 8 }, () => Array.from({ length: 8 }).fill(0)),
    size: { colCount: 0, rowCount: 0 },
  });

  const onCellMove = (rowIndex: number, colIndex: number) => {
    const newGrid = [...tablePicker.grid];

    for (let i = 0; i < newGrid.length; i++) {
      for (let j = 0; j < newGrid[i].length; j++) {
        newGrid[i][j] =
          i >= 0 && i <= rowIndex && j >= 0 && j <= colIndex ? 1 : 0;
      }
    }

    setTablePicker({
      grid: newGrid,
      size: { colCount: colIndex + 1, rowCount: rowIndex + 1 },
    });
  };

  return (
    <div
      className="flex! m-0 flex-col p-0"
      onClick={() => {
        tf.insert.table(tablePicker.size, { select: true });
        editor.tf.focus();
      }}
      role="button"
    >
      <div className="grid size-[130px] grid-cols-8 gap-0.5 p-1">
        {tablePicker.grid.map((rows, rowIndex) =>
          rows.map((value, columIndex) => (
            <div
              key={`(${rowIndex},${columIndex})`}
              className={cn(
                'col-span-1 size-3 border border-solid bg-secondary',
                !!value && 'border-current'
              )}
              onMouseMove={() => {
                onCellMove(rowIndex, columIndex);
              }}
            />
          ))
        )}
      </div>

      <div className="text-center text-current text-xs">
        {tablePicker.size.rowCount} x {tablePicker.size.colCount}
      </div>
    </div>
  );
}
