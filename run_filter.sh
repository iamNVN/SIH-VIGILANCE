
git filter-branch -f --env-filter '
  ADATE=$(echo $GIT_AUTHOR_DATE | awk "{print \$1}" | tr -d "@")
  ATZ=$(echo $GIT_AUTHOR_DATE | awk "{print \$2}")
  CDATE=$(echo $GIT_COMMITTER_DATE | awk "{print \$1}" | tr -d "@")
  CTZ=$(echo $GIT_COMMITTER_DATE | awk "{print \$2}")
  
  if [ "$ADATE" -gt 1788287340 ]; then
    NEW_ADATE=$(($ADATE - 172800))
    export GIT_AUTHOR_DATE="@${NEW_ADATE} ${ATZ}"
  fi
  
  if [ "$CDATE" -gt 1788287340 ]; then
    NEW_CDATE=$(($CDATE - 172800))
    export GIT_COMMITTER_DATE="@${NEW_CDATE} ${CTZ}"
  fi
' -- --all
