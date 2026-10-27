// Export de l'arbre affiché : SVG vectoriel, PNG haute résolution, PDF.


const PAD = 48;
const HEADER = 64;

async function toDataUrl(url: string): Promise<string | null> {
  try {
    const res = await fetch(url, { mode: "cors" });
    const blob = await res.blob();
    return await new Promise((resolve) => {
      const r = new FileReader();
      r.onload = () => resolve(r.result as string);
      r.onerror = () => resolve(null);
      r.readAsDataURL(blob);
    });
  } catch {
    return null;
  }
}

/** Construit un SVG autonome à partir du groupe affiché (sans transformation de zoom). */
export async function buildSvg(content: SVGGElement, heading: string): Promise<{ svg: string; w: number; h: number }> {
  const box = content.getBBox();
  const w = Math.ceil(box.width + PAD * 2);
  const h = Math.ceil(box.height + PAD * 2 + HEADER);
  const clone = content.cloneNode(true) as SVGGElement;
  clone.removeAttribute("transform");
  clone.setAttribute("transform", `translate(${PAD - box.x}, ${PAD + HEADER - box.y})`);

  // Les photos sont intégrées pour que le fichier reste lisible hors ligne.
  const images = Array.from(clone.querySelectorAll("image"));
  await Promise.all(
    images.map(async (img) => {
      const href = img.getAttribute("href");
      if (href && !href.startsWith("data:")) {
        const data = await toDataUrl(href);
        if (data) img.setAttribute("href", data);
        else img.remove();
      }
    }),
  );
  // Les pastilles « +N » n'ont pas de sens sur papier.
  clone.querySelectorAll(".texpand").forEach((n) => n.remove());

  const ns = "http://www.w3.org/2000/svg";
  const svg = document.createElementNS(ns, "svg");
  svg.setAttribute("xmlns", ns);
  svg.setAttribute("width", String(w));
  svg.setAttribute("height", String(h));
  svg.setAttribute("viewBox", `0 0 ${w} ${h}`);
  const bg = document.createElementNS(ns, "rect");
  bg.setAttribute("width", "100%");
  bg.setAttribute("height", "100%");
  bg.setAttribute("fill", "#FAFAFB");
  svg.appendChild(bg);
  const band = document.createElementNS(ns, "rect");
  band.setAttribute("width", "100%");
  band.setAttribute("height", "6");
  band.setAttribute("fill", "#1F2D5C");
  svg.appendChild(band);
  const title = document.createElementNS(ns, "text");
  title.setAttribute("x", String(PAD));
  title.setAttribute("y", String(PAD + 14));
  title.setAttribute("font-family", "'Literata Variable', Literata, Georgia, serif");
  title.setAttribute("font-size", "24");
  title.setAttribute("fill", "#141B33");
  title.textContent = heading;
  svg.appendChild(title);
  const date = document.createElementNS(ns, "text");
  date.setAttribute("x", String(PAD));
  date.setAttribute("y", String(PAD + 38));
  date.setAttribute("font-family", "system-ui, sans-serif");
  date.setAttribute("font-size", "13");
  date.setAttribute("fill", "#5D6379");
  date.textContent = `Exporté de Sheenu le ${new Date().toLocaleDateString("fr-FR", { dateStyle: "long" })}`;
  svg.appendChild(date);
  svg.appendChild(clone);
  return { svg: new XMLSerializer().serializeToString(svg), w, h };
}

function download(blob: Blob, filename: string) {
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(a.href), 2000);
}

async function rasterize(svg: string, w: number, h: number, scale: number): Promise<HTMLCanvasElement> {
  // Les navigateurs limitent la taille des canevas : on réduit l'échelle pour les très grands arbres.
  const maxSide = 16000;
  const s = Math.min(scale, maxSide / w, maxSide / h);
  const img = new Image();
  img.src = `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}`;
  await img.decode();
  const canvas = document.createElement("canvas");
  canvas.width = Math.round(w * s);
  canvas.height = Math.round(h * s);
  const ctx = canvas.getContext("2d")!;
  ctx.scale(s, s);
  ctx.drawImage(img, 0, 0, w, h);
  return canvas;
}

export async function exportTree(content: SVGGElement, format: "svg" | "png" | "pdf", heading: string, filename: string) {
  const { svg, w, h } = await buildSvg(content, heading);
  if (format === "svg") {
    download(new Blob([svg], { type: "image/svg+xml" }), `${filename}.svg`);
    return;
  }
  const canvas = await rasterize(svg, w, h, format === "png" ? 2 : 1.5);
  if (format === "png") {
    canvas.toBlob((b) => b && download(b, `${filename}.png`), "image/png");
    return;
  }
  const orientation = w >= h ? "landscape" : "portrait";
  const { jsPDF } = await import("jspdf");
  const pdf = new jsPDF({ orientation, unit: "pt", format: [w, h] });
  pdf.addImage(canvas.toDataURL("image/jpeg", 0.92), "JPEG", 0, 0, w, h);
  pdf.save(`${filename}.pdf`);
}

export { download };
