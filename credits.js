for (const item of globalThis.SOUND_CATALOG) {
  const section = document.createElement("section");
  section.className = "credit-item";
  const heading = document.createElement("h2");
  heading.textContent = `${item.name} · ${item.english}`;
  const author = document.createElement("p");
  author.textContent = `${item.credit.title} — ${item.credit.author}`;
  const links = document.createElement("p");
  const source = document.createElement("a");
  source.href = item.credit.source;
  source.textContent = "원본 및 제작자";
  links.append(source, " · ");
  if (item.credit.licenseUrl) {
    const license = document.createElement("a");
    license.href = item.credit.licenseUrl;
    license.textContent = item.credit.license;
    links.append(license);
  } else links.append(item.credit.license);
  const changes = document.createElement("p");
  changes.textContent = "변경 사항: Freesound 공개 고음질 MP3 미리듣기 파일 다운로드, 원본의 한 채널 선택, 최대 앞 15초 사용(1초 미만은 무음 추가), 음량·피크 조정 및 모노 MP3 변환. 가공된 음원에도 위 라이선스를 적용합니다.";
  section.append(heading, author, links, changes);
  document.getElementById("credits").append(section);
}
