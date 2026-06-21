import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Button } from "@/components/ui/button";

export interface QueueColumn<T> {
  key: string;
  header: string;
  render: (row: T) => React.ReactNode;
}

interface QueueTableProps<T> {
  columns: QueueColumn<T>[];
  data: T[];
  page: number;
  pages: number;
  onPageChange: (page: number) => void;
  emptyMessage?: string;
}

/**
 * Tabela genérica reutilizada pelas filas write/governance (e pela página de
 * governança). Recebe a definição de colunas e os dados já paginados pelo
 * backend; a navegação de página é delegada ao consumidor via `onPageChange`.
 */
export function QueueTable<T>({
  columns,
  data,
  page,
  pages,
  onPageChange,
  emptyMessage = "Nenhum job encontrado",
}: QueueTableProps<T>) {
  return (
    <div className="space-y-3">
      <div className="rounded-md border border-zinc-800">
        <Table>
          <TableHeader>
            <TableRow>
              {columns.map((col) => (
                <TableHead key={col.key}>{col.header}</TableHead>
              ))}
            </TableRow>
          </TableHeader>
          <TableBody>
            {data.length === 0 ? (
              <TableRow>
                <TableCell
                  colSpan={columns.length}
                  className="py-8 text-center text-zinc-500"
                >
                  {emptyMessage}
                </TableCell>
              </TableRow>
            ) : (
              data.map((row, i) => (
                <TableRow key={i}>
                  {columns.map((col) => (
                    <TableCell key={col.key}>{col.render(row)}</TableCell>
                  ))}
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>

      {pages > 1 && (
        <div className="flex items-center justify-end gap-2">
          <Button
            variant="outline"
            size="sm"
            disabled={page <= 1}
            onClick={() => onPageChange(page - 1)}
          >
            Anterior
          </Button>
          <span className="text-sm text-zinc-400">
            Página {page} de {pages}
          </span>
          <Button
            variant="outline"
            size="sm"
            disabled={page >= pages}
            onClick={() => onPageChange(page + 1)}
          >
            Próxima página
          </Button>
        </div>
      )}
    </div>
  );
}

export default QueueTable;
