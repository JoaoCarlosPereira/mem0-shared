import { render, act } from "@testing-library/react";
import { usePolling } from "@/hooks/usePolling";

function setHidden(value: boolean) {
  Object.defineProperty(document, "hidden", {
    configurable: true,
    get: () => value,
  });
}

function Harness({
  cb,
  interval,
  enabled,
}: {
  cb: () => void;
  interval: number;
  enabled?: boolean;
}) {
  usePolling(cb, interval, enabled);
  return null;
}

describe("usePolling", () => {
  beforeEach(() => {
    jest.useFakeTimers();
    setHidden(false);
  });

  afterEach(() => {
    jest.clearAllTimers();
    jest.useRealTimers();
  });

  it("chama a callback imediatamente ao montar e depois a cada intervalMs", () => {
    const cb = jest.fn();
    render(<Harness cb={cb} interval={1000} enabled={true} />);
    expect(cb).toHaveBeenCalledTimes(1);
    act(() => {
      jest.advanceTimersByTime(1000);
    });
    expect(cb).toHaveBeenCalledTimes(2);
    act(() => {
      jest.advanceTimersByTime(1000);
    });
    expect(cb).toHaveBeenCalledTimes(3);
  });

  it("não chama a callback com enabled=false", () => {
    const cb = jest.fn();
    render(<Harness cb={cb} interval={1000} enabled={false} />);
    act(() => {
      jest.advanceTimersByTime(5000);
    });
    expect(cb).not.toHaveBeenCalled();
  });

  it("limpa o intervalo ao desmontar (sem chamadas após unmount)", () => {
    const cb = jest.fn();
    const { unmount } = render(<Harness cb={cb} interval={1000} />);
    expect(cb).toHaveBeenCalledTimes(1);
    unmount();
    act(() => {
      jest.advanceTimersByTime(5000);
    });
    expect(cb).toHaveBeenCalledTimes(1);
  });

  it("não chama a callback quando document.hidden = true", () => {
    const cb = jest.fn();
    setHidden(true);
    render(<Harness cb={cb} interval={1000} />);
    act(() => {
      jest.advanceTimersByTime(3000);
    });
    expect(cb).not.toHaveBeenCalled();
  });

  it("chama a callback novamente quando document.hidden volta a false", () => {
    const cb = jest.fn();
    setHidden(true);
    render(<Harness cb={cb} interval={1000} />);
    act(() => {
      jest.advanceTimersByTime(2000);
    });
    expect(cb).not.toHaveBeenCalled();

    // Aba volta ao foco → visibilitychange dispara a callback
    setHidden(false);
    act(() => {
      document.dispatchEvent(new Event("visibilitychange"));
    });
    expect(cb).toHaveBeenCalledTimes(1);
  });

  it("reinicia o intervalo ao alterar intervalMs via re-render", () => {
    const cb = jest.fn();
    const { rerender } = render(<Harness cb={cb} interval={1000} />);
    expect(cb).toHaveBeenCalledTimes(1);
    act(() => {
      jest.advanceTimersByTime(1000);
    });
    expect(cb).toHaveBeenCalledTimes(2);

    rerender(<Harness cb={cb} interval={500} />);
    expect(cb).toHaveBeenCalledTimes(3);
    act(() => {
      jest.advanceTimersByTime(500);
    });
    expect(cb).toHaveBeenCalledTimes(4);
  });
});
