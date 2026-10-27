// Albums photo de la famille : couvertures, création d'un album.

import { PlusOutlined } from "@ant-design/icons";
import { App, Empty, Form, Input, InputNumber, Modal, Button, Spin } from "antd";
import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router";
import { PageHead } from "../../components/AppShell";
import { api } from "../../lib/api";
import { count } from "../../lib/text";
import type { AlbumCard } from "../../types";
import { MemoryNav } from "./components/MemoryNav";

export function AlbumsPage() {
  const { message } = App.useApp();
  const navigate = useNavigate();
  const [items, setItems] = useState<AlbumCard[] | null>(null);
  const [creating, setCreating] = useState(false);
  const [form] = Form.useForm();

  useEffect(() => void api<AlbumCard[]>("/albums").then(setItems), []);

  const create = async (v: { title: string; year?: number; description?: string }) => {
    const a = await api<AlbumCard>("/albums", { method: "POST", body: v });
    message.success("Album créé. Ajoutez-y des photos.");
    navigate(`/memoire/albums/${a.id}`);
  };

  return (
    <div className="page">
      <PageHead
        title="Mémoire de la famille"
        lead="Les photos de famille rangées par événement. Chacun peut ajouter les siennes et reconnaître les personnes."
        actions={
          <Button type="primary" icon={<PlusOutlined />} onClick={() => setCreating(true)}>
            Nouvel album
          </Button>
        }
      />
      <MemoryNav />
      {!items ? (
        <Spin style={{ display: "block", margin: 40 }} />
      ) : items.length === 0 ? (
        <Empty description="Aucun album. Créez-en un pour un mariage, une fête, ou les vieilles photos du village." />
      ) : (
        <div className="albums">
          {items.map((a) => (
            <Link key={a.id} to={`/memoire/albums/${a.id}`} className="album-card">
              <span className="album-card__cover">{a.cover_url ? <img src={a.cover_url} alt="" loading="lazy" /> : null}</span>
              <span className="album-card__title">{a.title}</span>
              <span className="years">
                {[a.year, a.count ? count(a.count, "photo") : "aucune photo"].filter(Boolean).join(", ")}
              </span>
            </Link>
          ))}
        </div>
      )}
      <Modal open={creating} title="Nouvel album" okText="Créer" cancelText="Annuler" onOk={() => form.submit()} onCancel={() => setCreating(false)} destroyOnHidden>
        <Form form={form} layout="vertical" onFinish={create} requiredMark={false}>
          <Form.Item name="title" label="Titre" rules={[{ required: true, min: 2, message: "Donnez un titre." }]}>
            <Input placeholder="Mariage de Mama Habiba, 1975" />
          </Form.Item>
          <Form.Item name="year" label="Année">
            <InputNumber min={1000} max={2100} style={{ width: 160 }} />
          </Form.Item>
          <Form.Item name="description" label="Description">
            <Input.TextArea autoSize={{ minRows: 2, maxRows: 6 }} />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
