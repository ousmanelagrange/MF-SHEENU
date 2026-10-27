import { Alert, App, Button, Checkbox, DatePicker, Form, Input, InputNumber, Select, Spin } from "antd";
import dayjs, { type Dayjs } from "dayjs";
import { useEffect, useState } from "react";
import { useNavigate, useParams, useSearchParams } from "react-router";
import { api } from "../api";
import { PageHead } from "../components/AppShell";
import { PersonLine } from "../components/Person";
import type { PersonDetail, PersonSummary } from "../types";

// eslint-disable-next-line @typescript-eslint/no-explicit-any
type Values = Record<string, any> & { birth_date?: Dayjs; death_date?: Dayjs; is_living?: boolean };

export function PersonFormPage() {
  const { id } = useParams();
  const editing = !!id;
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const { message } = App.useApp();
  const [form] = Form.useForm<Values>();
  const [loading, setLoading] = useState(editing);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [context, setContext] = useState<{ label: string; person: PersonSummary }[]>([]);
  const living = Form.useWatch("is_living", form) ?? true;

  const parent = params.get("parent");
  const parent2 = params.get("parent2");
  const spouse = params.get("conjoint");
  const child = params.get("enfant");

  useEffect(() => {
    if (editing) {
      api<PersonDetail>(`/persons/${id}`).then((p) => {
        form.setFieldsValue({
          ...p,
          birth_date: p.birth_date ? dayjs(p.birth_date) : undefined,
          death_date: p.death_date ? dayjs(p.death_date) : undefined,
        } as unknown as Values);
        setLoading(false);
      });
    } else {
      const refs: [string | null, string][] = [
        [parent, "Enfant de"],
        [parent2, "et de"],
        [spouse, "Conjoint de"],
        [child, "Parent de"],
      ];
      Promise.all(
        refs
          .filter(([pid]) => pid)
          .map(async ([pid, label]) => ({ label, person: await api<PersonSummary>(`/persons/${pid}`) })),
      ).then((ctx) => {
        setContext(ctx);
        const lastName = ctx.find((c) => c.label === "Enfant de")?.person.last_name;
        if (lastName) form.setFieldValue("last_name", lastName);
      });
    }
  }, [id, editing, parent, parent2, spouse, child, form]);

  const submit = async (v: Values) => {
    setSaving(true);
    setError(null);
    const body = {
      ...v,
      birth_date: v.birth_date ? v.birth_date.format("YYYY-MM-DD") : null,
      death_date: v.death_date ? v.death_date.format("YYYY-MM-DD") : null,
      birth_year: v.birth_date ? null : (v.birth_year ?? null),
      death_year: v.death_date ? null : (v.death_year ?? null),
    };
    try {
      let saved: PersonDetail;
      if (editing) {
        saved = await api<PersonDetail>(`/persons/${id}`, { method: "PATCH", body });
      } else {
        saved = await api<PersonDetail>("/persons", {
          method: "POST",
          body: {
            ...body,
            parent_ids: [parent, parent2].filter(Boolean),
            spouse_id: spouse ?? undefined,
          },
        });
        if (child) {
          await api("/relations/parent-child", {
            method: "POST",
            body: { parent_id: saved.id, child_id: child },
          });
        }
      }
      message.success(editing ? "Modifications enregistrées." : "Fiche créée.");
      navigate(`/personnes/${saved.id}`);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setSaving(false);
    }
  };

  if (loading) return <Spin style={{ margin: 48 }} />;

  return (
    <div className="page" style={{ maxWidth: 760 }}>
      <PageHead
        title={editing ? "Modifier la fiche" : "Nouvelle personne"}
        lead={editing ? undefined : "Seul le prénom est obligatoire. Une année approximative suffit si la date exacte est inconnue."}
      />
      {context.length > 0 && (
        <ul className="kin-list" style={{ marginBottom: 28 }}>
          {context.map((c) => (
            <li key={c.person.id}>
              <div className="kin-item">
                <PersonLine person={c.person} link={false} size={28} />
                <span className="kin-meta">{c.label}</span>
              </div>
            </li>
          ))}
        </ul>
      )}
      {error && <Alert type="error" showIcon message={error} style={{ marginBottom: 16 }} />}
      <Form
        form={form}
        layout="vertical"
        requiredMark={false}
        onFinish={submit}
        initialValues={{ sex: "U", is_living: true, contact_visibility: "family" }}
      >
        <div className="form-grid">
          <Form.Item name="first_name" label="Prénom" rules={[{ required: true, message: "Le prénom est obligatoire." }]}>
            <Input />
          </Form.Item>
          <Form.Item name="last_name" label="Nom">
            <Input />
          </Form.Item>
          <Form.Item name="traditional_name" label="Nom traditionnel">
            <Input />
          </Form.Item>
          <Form.Item name="nickname" label="Surnom">
            <Input />
          </Form.Item>
          <Form.Item name="sex" label="Sexe">
            <Select
              options={[
                { value: "M", label: "Homme" },
                { value: "F", label: "Femme" },
                { value: "U", label: "Non précisé" },
              ]}
            />
          </Form.Item>
          <Form.Item name="is_living" valuePropName="checked" label=" ">
            <Checkbox>En vie</Checkbox>
          </Form.Item>
          <Form.Item name="birth_date" label="Date de naissance">
            <DatePicker style={{ width: "100%" }} format="DD/MM/YYYY" />
          </Form.Item>
          <Form.Item name="birth_year" label="ou année approximative">
            <InputNumber style={{ width: "100%" }} min={1000} max={2200} />
          </Form.Item>
          <Form.Item name="birth_place" label="Lieu de naissance">
            <Input />
          </Form.Item>
          <Form.Item name="village" label="Village d'origine">
            <Input />
          </Form.Item>
          {!living && (
            <>
              <Form.Item name="death_date" label="Date de décès">
                <DatePicker style={{ width: "100%" }} format="DD/MM/YYYY" />
              </Form.Item>
              <Form.Item name="death_year" label="ou année approximative">
                <InputNumber style={{ width: "100%" }} min={1000} max={2200} />
              </Form.Item>
              <Form.Item name="death_place" label="Lieu de décès">
                <Input />
              </Form.Item>
            </>
          )}
          <Form.Item name="country" label="Pays de résidence">
            <Input />
          </Form.Item>
        </div>
        {living && (
          <div className="form-grid">
            <Form.Item name="phone" label="Téléphone">
              <Input />
            </Form.Item>
            <Form.Item name="email" label="E-mail">
              <Input />
            </Form.Item>
            <Form.Item name="contact_visibility" label="Qui voit ces coordonnées">
              <Select
                options={[
                  { value: "family", label: "Toute la famille" },
                  { value: "branch", label: "Sa branche" },
                  { value: "board", label: "Le bureau seulement" },
                  { value: "private", label: "Personne" },
                ]}
              />
            </Form.Item>
          </div>
        )}
        <Form.Item name="biography" label="Histoire" extra="Ce que la famille raconte de cette personne.">
          <Input.TextArea autoSize={{ minRows: 4, maxRows: 14 }} />
        </Form.Item>
        <div style={{ display: "flex", gap: 8 }}>
          <Button type="primary" htmlType="submit" loading={saving}>
            {editing ? "Enregistrer" : "Créer la fiche"}
          </Button>
          <Button onClick={() => navigate(-1)}>Annuler</Button>
        </div>
      </Form>
    </div>
  );
}
