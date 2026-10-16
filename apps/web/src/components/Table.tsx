import { useMemo, useState, type ReactNode } from "react";

import { LoadingPanel } from "./Loading";

import "./components.css";

export interface Column<T> {
  key: string;
  header: ReactNode;
  render: (row: T) => ReactNode;
  sortable?: boolean;
  sortValue?: (row: T) => string | number;
  align?: "left" | "right" | "center";
  width?: string;
  className?: string;
}

export interface DataTableProps<T> {
  columns: Column<T>[];
  rows: T[];
  rowKey: (row: T, index: number) => string;
  loading?: boolean;
  empty?: ReactNode;
  onRowClick?: (row: T) => void;
  initialSortKey?: string;
  initialSortDir?: "asc" | "desc";
  caption?: string;
}

type SortState = { key: string; dir: "asc" | "desc" } | null;

export function DataTable<T>({
  columns,
  rows,
  rowKey,
  loading = false,
  empty,
  onRowClick,
  initialSortKey,
  initialSortDir = "desc",
  caption,
}: DataTableProps<T>) {
  const [sort, setSort] = useState<SortState>(
    initialSortKey ? { key: initialSortKey, dir: initialSortDir } : null,
  );

  const sorted = useMemo(() => {
    if (!sort) return rows;
    const column = columns.find((c) => c.key === sort.key);
    if (!column) return rows;
    const valueOf = (row: T): string | number => {
      if (column.sortValue) return column.sortValue(row);
      const rendered = column.render(row);
      if (typeof rendered === "string" || typeof rendered === "number") return rendered;
      return "";
    };
    const copy = [...rows];
    copy.sort((a, b) => {
      const va = valueOf(a);
      const vb = valueOf(b);
      if (va < vb) return sort.dir === "asc" ? -1 : 1;
      if (va > vb) return sort.dir === "asc" ? 1 : -1;
      return 0;
    });
    return copy;
  }, [rows, sort, columns]);

  const toggle = (key: string) => {
    setSort((current) => {
      if (current?.key === key) {
        return { key, dir: current.dir === "asc" ? "desc" : "asc" };
      }
      return { key, dir: "desc" };
    });
  };

  if (loading) return <LoadingPanel rows={5} title={false} />;

  return (
    <div className="table-wrap">
      <table className="data-table">
        {caption && <caption className="sr-only">{caption}</caption>}
        <thead>
          <tr>
            {columns.map((column) => {
              const active = sort?.key === column.key;
              return (
                <th
                  key={column.key}
                  scope="col"
                  style={{ width: column.width }}
                  className={`${column.align ? `align-${column.align}` : ""} ${
                    column.sortable ? "sortable" : ""
                  } ${active ? "sorted" : ""}`}
                  aria-sort={
                    active ? (sort?.dir === "asc" ? "ascending" : "descending") : undefined
                  }
                >
                  {column.sortable ? (
                    <button
                      type="button"
                      className="th-button"
                      onClick={() => toggle(column.key)}
                    >
                      <span>{column.header}</span>
                      <span className="sort-arrow" aria-hidden="true">
                        {active ? (sort?.dir === "asc" ? "\u2191" : "\u2193") : "\u2195"}
                      </span>
                    </button>
                  ) : (
                    column.header
                  )}
                </th>
              );
            })}
          </tr>
        </thead>
        <tbody>
          {sorted.length === 0 && (
            <tr>
              <td colSpan={columns.length} className="table-empty-cell">
                {empty ?? "No records."}
              </td>
            </tr>
          )}
          {sorted.map((row, index) => (
            <tr
              key={rowKey(row, index)}
              className={onRowClick ? "clickable" : undefined}
              onClick={onRowClick ? () => onRowClick(row) : undefined}
              tabIndex={onRowClick ? 0 : undefined}
              onKeyDown={
                onRowClick
                  ? (event) => {
                      if (event.key === "Enter" || event.key === " ") {
                        event.preventDefault();
                        onRowClick(row);
                      }
                    }
                  : undefined
              }
            >
              {columns.map((column) => (
                <td
                  key={column.key}
                  className={`${column.align ? `align-${column.align}` : ""} ${
                    column.className ?? ""
                  }`}
                >
                  {column.render(row)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
