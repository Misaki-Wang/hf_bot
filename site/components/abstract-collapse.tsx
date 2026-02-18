import CollapsiblePanel from './collapsible-panel';

interface AbstractCollapseProps {
  abstract: string;
}

export default function AbstractCollapse({ abstract }: AbstractCollapseProps) {
  const text = (abstract || '').trim();

  if (!text) {
    return (
      <section className="abstract-block">
        <div className="meta panel-empty">Abstract: N/A</div>
      </section>
    );
  }

  return (
    <CollapsiblePanel
      title={
        <span className="panel-title panel-title--abstract">Abstract</span>
      }
      defaultOpen={false}
      containerClassName="abstract-block"
      toggleClassName="panel-toggle"
      arrowClassName="panel-arrow"
      contentClassName="panel-content paper-summary abstract-text"
    >
      {text}
    </CollapsiblePanel>
  );
}
