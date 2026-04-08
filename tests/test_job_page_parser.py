from job_assist_skill.scraper.scrapers.job import parse_job_page_html


def test_parse_job_page_html_uses_ld_json_and_public_metadata():
    html = """
    <html>
      <head>
        <script type="application/ld+json">
          {
            "@context": "http://schema.org",
            "@type": "JobPosting",
            "title": "Operations Manager - KSA & UAE",
            "description": "<p>Lead operations across KSA and UAE.</p>",
            "datePosted": "2026-04-07T22:06:35.000Z",
            "hiringOrganization": {
              "@type": "Organization",
              "name": "Stryker",
              "sameAs": "https://www.linkedin.com/company/stryker"
            },
            "jobLocation": {
              "@type": "Place",
              "address": {
                "@type": "PostalAddress",
                "addressLocality": "Riyadh",
                "addressCountry": "SA"
              }
            }
          }
        </script>
      </head>
      <body>
        <h1>Operations Manager - KSA & UAE</h1>
        <div class="topcard__flavor-row">
          <span class="topcard__flavor">
            <a data-tracking-control-name="public_jobs_topcard-org-name" href="https://www.linkedin.com/company/stryker?trk=public_jobs_topcard-org-name">Stryker</a>
          </span>
          <span class="topcard__flavor topcard__flavor--bullet">Riyadh, Riyadh, Saudi Arabia</span>
        </div>
        <div class="topcard__flavor-row">
          <span class="posted-time-ago__text posted-time-ago__text--new topcard__flavor--metadata">19 hours ago</span>
          <figure class="num-applicants__figure topcard__flavor--metadata topcard__flavor--bullet">
            <figcaption class="num-applicants__caption">Over 200 applicants</figcaption>
          </figure>
        </div>
        <div class="description__text description__text--rich">
          <section class="show-more-less-html">
            <div class="show-more-less-html__markup show-more-less-html__markup--clamp-after-5">
              <p>Lead operations across KSA and UAE.</p>
            </div>
          </section>
        </div>
      </body>
    </html>
    """

    parsed = parse_job_page_html(html)

    assert parsed["job_title"] == "Operations Manager - KSA & UAE"
    assert parsed["company"] == "Stryker"
    assert parsed["location"] == "Riyadh, Riyadh, Saudi Arabia"
    assert parsed["posted_date"] == "19 hours ago"
    assert parsed["applicant_count"] == "Over 200 applicants"
    assert "Lead operations across KSA and UAE." in parsed["job_description"]
