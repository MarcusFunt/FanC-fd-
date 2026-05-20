import CodeMirror from "@uiw/react-codemirror";
import { yaml as yamlLanguage } from "@codemirror/lang-yaml";

interface YamlEditorProps {
  value: string;
  onChange: (value: string) => void;
}

export default function YamlEditor({ value, onChange }: YamlEditorProps) {
  return (
    <div className="yaml-editor">
      <CodeMirror
        value={value}
        height="100%"
        basicSetup={{
          foldGutter: true,
          lineNumbers: true,
          highlightActiveLine: false
        }}
        extensions={[yamlLanguage()]}
        onChange={onChange}
      />
    </div>
  );
}

